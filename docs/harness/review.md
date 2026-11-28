# `codex/workflow-harness-wip` 分支 Code Review 意见

- **评审对象**：`codex/workflow-harness-wip@ab6ac8e`（相对父分支 `codex/workflow-workbench@8789766` 的 4 个提交，29 个文件，+2283 / -38 行）
- **对比主干**：`main@8cba4a7`（共同祖先 `2189c97`，落后 PR #5/#6 媒体编辑、PR #7 PR 规范、PR #8 Gemini Review）
- **评审日期**：2026-11-28

## 总体结论

架构分层清晰：`ToolBridge` 回环鉴权通道 + 每轮绑定 `EditorTools` 快照 + `editor_revision`/`if_revision` 乐观并发保护，方向扎实；`tests/test_web_api.py` 中基于真实 `dsh` 进程的跨轮状态/停止/LRU/清理集成测试质量很高；`docs/harness/` 三篇设计文档内部数据（77 工具、74 路径、93 HTTP 操作、难度与分类统计、相对链接）全部校验一致。

当前合并或上线前需要优先解决 **5 项 P0**（核心工具缺陷、状态机/并发锁风险、容器部署缺 `pnpm` 与代理漂移）与 **4 项 P1**（校验漏洞、插件事件污染、前端边界与目录泄漏），并在 rebase 到 `main` 后补齐 `video_from` 等新字段适配与单元测试。

---

## P0 / 高优先级问题（合入或上线前必改）

### 1. `add_step` 添加 `image_gen` 节点时默认直接失败（已内存复现确认）
- **位置**：`draw_studio/workflows/agent_tools.py:47-48, 119-123, 148-161, 226-228`、`draw_studio/workflows/definitions.py:94`
- **现象**：`STEP_CATALOG` 中 `image_gen` 的 `default_config` 默认携带 `"ref_sources": ["web_refs", "character_assets"]`。`_apply()` 在 `add_step` 自动清理/重连上游引用时，仅处理了 `SOURCE_TYPES` 中的 4 个单值字段（`scenes_from`、`keyframe_from`、`prompts_from`、`clips_from`），遗漏了 `ref_sources`。随后的 `_bad_sources()` 会校验 `ref_sources` 和 `extra_ref_sources`，导致在任何不具备 `web_refs` 与 `character_assets` 两个前置步骤的工作流（例如空白工作流或 `builtin:storyboard-short`）中，调用 `add_step(step_type="image_gen")` 且未显式覆盖 `config.ref_sources` 时必然报错拒绝。
- **修复建议**：在 `add_step` 中同步对**继承自默认配置**的 `ref_sources` / `extra_ref_sources` 做过滤，仅保留存在于 `earlier` 且类型属于 `{"asset_input", "web_asset_fetch", "image_gen"}` 的前置步骤 ID；若调用方在 `op["config"]` 中**显式传入**了不存在或非法上游，仍继续报错，不要静默吞掉。

### 2. `_wait_turn()` 取消、晚到 `idle` 与异常回合状态机漏洞（已内存复现确认）
- **位置**：`draw_studio/workflows/copilot.py:129-134, 150-212`、`draw_studio/workflows/agent_bridge.py:58-69`、`draw_studio/workflows/dsh_tools.mjs:34-43`
- **现象**：
  1. **晚到 `idle` 导致进程带病复用**：`copilot.py:183-187` 收到 `session.status == "idle"` 时，`if cancel.is_set(): raise TurnStopped` 未检查 `admitted` 或是否已发过 `interrupt()`；而 `run()`（`L154-156`）对 `TurnStopped` 不关闭进程。直接向 `_wait_turn` 输入已置位的 `cancel` 与同 session 的 `idle`（无接纳/结束事件）即可复现提前返回 `TurnStopped`，若真实乱序发生，新提交的 `session_prompt` 会残留在后台继续运行。
  2. **`/stop` 对未激活 agent 静默返回 204，且两端协议耦合**：`dsh_tools.mjs:40` 使用 `ctx.agents.get(...)?.cancel({ kind: 'user' })`，当 agent 缺席时仍返回 `204`；而 `ToolBridge.interrupt()`（`agent_bridge.py:66`）会把所有非 `204` 响应直接转为 `RuntimeError` 进而关掉进程。
  3. **异常回合可能挂死 180 秒**：若 `dsh` 因模型/鉴权/序列化失败直接回到 `session.status == "idle"`，但未发出匹配 `receipt` 的 `agent/inbox/spliced` 或未发出 `turn/end`，`L188-191` 会跳过该 `idle` 并循环等待直到 180 秒超时。
  4. **`native-session` 恢复失败后反复重试**：`L133-134` 会先调 native `get_working_directory()` 创建会话再写 `native-session` 标记；但若后续会话日志缺失、损坏或仍被占用，`resume_session()` 失败后会因标记持续存在而反复重试。
- **修复建议**：
  - 区分“已发 cancel 且已确认本轮被接纳/取消”与“未确认的晚到 idle”；在未确认已停稳的情况下宁可关闭进程，不能复用脏进程。
  - `dsh_tools.mjs` 与 `ToolBridge.interrupt()` 两端协同区分**「已请求取消 / 已空闲 / 无法确认」**三种状态，不能只改 JS 状态码否则会误关进程。
  - 监听并处理 `dsh` 错误事件/状态，避免未发 `turn/end` 的失败轮次挂死 180 秒。
  - 恢复失败时区分记录缺失、损坏和占用；对损坏文件应**保留现场**（例如转存/重命名备份）再回退新建会话，避免直接删除可抢救的历史。

### 3. `HarnessSessions` 锁竞争、阻塞持锁销毁与 `forget()` 竞态
- **位置**：`draw_studio/workflows/copilot.py:224-286`
- **现象**：
  1. **`forget()` 等待循环漏发取消信号**：`L263-274` 仅在 `wait_for(lambda: not slot.active)` 之前调用了一次 `slot.active[1].set()`。等待释放锁期间，若有新请求拿到同一 `key` 的 `lease` 并设置新的 `cancel` 事件，`forget()` 不会取消新轮次，可能卡住 `DELETE /api/workflows/runs/{run_id}` 长达 180 秒。
  2. **持有 `self.changed` 期间执行阻塞 I/O 与子进程清理，且异常会造成唤醒丢失**：`lease()` 淘汰空闲槽位（`L239`）、非持久化会话退出（`L251`）以及 `forget()`（`L271`）都在 `with self.changed:` 内调用 `dispose()`（包含关闭子进程和 `server.shutdown(); thread.join()`），阻塞整个会话池。若 `L251` 的 `slot.dispose()` 抛异常，还会跳过 `L253` 的 `self.changed.notify_all()`，导致 `forget()` / `shutdown()` 永久死锁。
- **修复建议**：
  - 引入按 `key` 的 `forgetting` 状态集合阻止删除中的会话被重新 `lease()`，并在 `while` 循环中重新检查并取消活跃槽位。
  - 锁内仅摘除槽位和更新状态，将 `dispose()` 与 `shutil.rmtree()` 移至锁外执行；在 `finally` 中保证 `notify_all()` 必定调用。

### 4. 共享 `sdk-minimal` profile 在多进程运行中被 `pnpm` 热改 & 全局锁阻塞插件查询
- **位置**：`draw_studio/workflows/copilot.py:102-138`、`draw_studio/workflows/agent_plugins.py:33-69`、`web/src/features/workflow/AgentPlugins.tsx:35-41`
- **现象**：
  1. `HarnessSessions` 允许最多 4 个工作流并发运行各自的 `dsh` 进程，共享同一份 `profiles/sdk-minimal` 目录。`AgentPlugins.tsx` 仅检查当前标签页的 `busy` 状态，后端 `change_plugin()` 不检查是否有其他活跃 `dsh` 进程，可能在别的会话运行期间通过 `pnpm` 改写或删除 `node_modules`。
  2. `Conversation.prepare()` 在整个 `harness.start()`（最长 20 秒）期间持续持有 `PROFILE_LOCK`，而只读的 `agent_plugins.inventory()` 也获取同一把锁，导致任意工作流冷启动或装插件时阻塞所有用户的插件列表查询。
- **修复建议**：
  - 插件安装与卸载发布到**版本化 profile 目录**，让已运行的 `dsh` 进程继续锚定原目录（同时解决 `pnpm` 原地踩坏 `node_modules` 和打断其他会话插件内存两个问题），新会话或用户显式重载时再切新版本。
  - 缩小锁粒度或使用原子快照，避免 `inventory()` 被冷启动阻塞。

### 5. 生产 Docker 镜像缺少 `pnpm`、代理环境变量漂移与模型预算硬编码
- **位置**：`Dockerfile:8-41`、`requirements.txt:8`、`draw_studio/workflows/agent_plugins.py:53-60`、`draw_studio/workflows/copilot.py:33-38, 62-67, 123-126`、`draw_studio/proxy.py:124`、`draw_studio/llm.py:243`
- **现象**：
  1. **Docker 镜像无 `node`/`pnpm`**：`Dockerfile` 运行镜像为 `python:3.13-slim`，只安装了 `ffmpeg` 和 Python 依赖。生产容器内点击「安装/卸载插件」必然返回 409 `"管理插件需要在 Studio 服务器安装 pnpm"`（普通编排也需在目标 Linux 容器内单独做一次冒烟验证）。同时 `requirements.txt` 暂锁预发布包 `deepseek-harness-sdk==0.2.2rc2`，后续应在适配层隔离与回归门禁下受控跟进官方更新。
  2. **代理配置漂移与本机模型代理行为需核验**：Studio 通过修改全局 `os.environ["HTTP_PROXY"]/HTTPS_PROXY` 切换出口代理（`proxy.py:124` 已对 loopback 设置 `NO_PROXY`），且 `llm.py:243` 对本机/私网地址显式禁用代理。但 `_profile_signature()` 未包含代理环境变量，切换代理后常驻 `dsh` 进程会一直沿用旧环境变量；且本机模型与回环桥的代理绕行行为需分开实测验证。
  3. **三处模型窗口/输出预算硬编码偏小**：`copilot.py` 硬编码了 `contextWindow=32768`、`maxTokens=4096` 和 `DeepSeekHarness(..., max_tokens=2048)`；且 `0.2.2rc2` 仅在 `initialize` 时传 `maxTokens`、`session_prompt()` 不支持逐轮覆盖。静态注入更多工具与范例后会挤占窗口或截断批量编辑。
- **修复建议**：
  - 明确生产镜像策略：要么在运行镜像提供 `pnpm`（或预装可信本地插件），要么在无 `pnpm` 环境下给出清晰能力降级说明，并补一条容器冒烟验证。
  - 将生效的代理环境变量纳入 `_profile_signature()`；当 `is_local_or_private_host(urlsplit(provider.base).hostname or "")` 为真时，确保 `dsh` 模型请求绕过出口代理。
  - 将 `contextWindow`/`maxTokens` 改为读取 provider/模型部署配置，并为常驻会话一次性给足输出预算（如部署允许下 4K–8K 起测），避免为调预算重启进程丢失插件内存。

---

## P1 / 中优先级问题（建议一并修复）

### 6. `agent_tools.py` 参数校验漏洞与 `run_request` 失效
- **位置**：`draw_studio/workflows/agent_tools.py:21-22, 133-145, 207-235`
- **现象**：
  1. **未拒绝 `NaN`/`Infinity`**：浮点配置项（如 `cfg`、`fade_s`）未用 `math.isfinite()` 校验，可能导致 `json.dumps` 输出非法 JSON（`NaN`）破坏前端 NDJSON 解析。
  2. **整型字段可能被写入 `float`**：默认值为 `int`（如 `scene_count: 3`）且入参为 `5.0` 时，`float(5.0).is_integer()` 通过但未转换为 `int(value)`。
  3. **列表元素与数值边界缺失**：`gpu_pool`、`loras`、`round_ids`、`clip_round_ids` 仅校验了 `type(value) is list`（例如 `gpu_pool: [123]` 可穿透 `_apply()` 和 `definitions.py:515` 直接落盘）；`scene_count`、`num_frames`、`width`/`height`、`fps` 等无正数或合理区间校验。
  4. **`offload_mode` 不可由 Agent 新增**：`video_gen` 的 `default_config` 未包含 `offload_mode`，导致 Agent 无法在新 `video_gen` 节点上设置该字段。
  5. **同轮 `studio_request_run` 后继续编辑可能留下失效请求**：若 Agent 先调用 `studio_request_run(step_id="script")`，后调用 `studio_edit_workflow` 删除 `"script"` 或禁用全部步骤，`self.run_request` 不会清空或复检。
  6. `OPERATIONS["add_step"]` 缺少 `"position"`（`update_step` 已支持）。
- **修复建议**：补齐 `math.isfinite`、`int()` 强转、列表元素类型校验与关键数值范围校验；`studio_edit_workflow` 成功后同步校验或清理失效的 `self.run_request`；允许 `add_step` 携带 `position` 并对齐 `offload_mode`。

### 7. `studio_shot_timing` 插件回调污染 UI 工具徽章与调用配额
- **位置**：`draw_studio/workflows/plugins/shot-timing/index.mjs:11-15`、`draw_studio/workflows/agent_bridge.py:50-56`、`draw_studio/workflows/copilot.py:204-210`
- **现象**：`studio_shot_timing` 通过 `POST /tool {name: "studio_read_workflow"}` 读当前工作流，导致每次调用插件都会额外向前端发送一个模型并未调用的「读取工作流」工具徽章，并消耗 1 次 32 次的轮次调用配额；此外 `copilot.py:204-210` 硬编码仅监听 `agent_plugins.TOOL`，无法泛化到其他插件。
- **修复建议**：为插件内部上下文读取提供独立只读端点（如 `/context`）或不计入用户工具事件的内部标志；`copilot.py` 转发所有非内置桥接工具的 `tool/call` → `tool/result` 事件。

### 8. 前端浮窗与草稿交互边界缺陷
- **位置**：`web/src/features/workflow/WorkflowAgent.tsx:53-63, 93, 117-121, 167`、`web/src/features/workflow/Workflow.tsx:150-181, 379`、`web/src/features/workflow/AgentPlugins.tsx:12-16`
- **现象**：
  1. **历史合并倒序**：`WorkflowAgent.tsx:57-60` 将服务端拉回的新记录一律拼在 `current` 之前（`[...saved.filter(...), ...current]`），跨标签页对话后重开浮窗会出现新消息跑到旧消息上面的时间倒序问题。
  2. **草稿部分提交失败后无法继续对话**：`DraftCanvas.start()` 若 `createRun(request_id)` 成功但 `uploadAsset` 失败，页面仍留在 `DraftCanvas` 且未调用 `loadWf()` 刷新侧栏；此时在浮窗发消息会被 `api/workflows.py:111-112` 以 409 拒绝（“该草稿已经保存，请打开对应运行记录后继续对话”）。
  3. **点击「试算片长」清掉用户输入草稿**：`send(text = input)` 无条件执行 `setInput('')`，从插件页点「试算片长」会清掉对话输入框里尚未发送的草稿文本。
  4. **Portal 绕过 `inert`**：`WorkflowAgent` 通过 `createPortal` 渲染在 `document.body`，`.run` 上的 `inert={starting}` / `inert={acting}` 无法阻止提交期间并发操作浮窗。
  5. **Mock 模式插件页报错**：`AgentPlugins` 未处理 `__MOCK__`，且 `web/src/mock/server.ts` 缺少 `/api/workflows/agent/plugins` 路由。
- **修复建议**：合并历史记录时按服务端顺序为主并仅保留本地未落盘的 `working`/`error`/`stopped` 项；草稿 `createRun` 后若上传失败应同步 `loadWf()` 或提示切换至该草稿运行；仅当 `text === input` 时清空输入框；将 `acting`/`starting` 传入 `WorkflowAgent` 禁用提交；在 `AgentPlugins` 或 `mock/server.ts` 补齐 mock 兜底。

### 9. 孤儿草稿对话目录泄漏与 `recent.json` 损坏无容错
- **位置**：`draw_studio/workflows/copilot.py:55-59, 76, 94-100`
- **现象**：
  1. 在 `DraftCanvas` 模板页每次打开都会分配新 `draftId`，只要发过一轮消息就会在 `$QP_ROOT/private/workflow-harness/conversations/wr_<id>/` 留下持久目录和会话日志；若用户未保存为运行记录，目录永不回收。
  2. `recent_exchanges()` 未捕获 `JSONDecodeError` 或校验列表结构，文件损坏会导致 `GET /agent/conversations/{key}` 永久返回 400 且后续 `remember()` 持续失败。
- **修复建议**：在 `recent_exchanges()` 捕获 `OSError`/`ValueError` 并校验为 `list`（损坏时回退 `[]` 并记日志）；为孤儿草稿目录增加启动或定时 TTL 清理（与 `store.auto_purge()` 类似，跳过仍有对应 `runs/<id>` 的目录）。

---

## P2 / 低优先级与工程细节

- **事件循环关闭竞态**：`copilot.py:294-296` 的 `emit()` 建议捕获 `loop.call_soon_threadsafe()` 的 `RuntimeError`，避免服务关闭瞬间在 worker 线程抛出未捕获异常。
- **`ToolBridge` 异常兜底**：`agent_bridge.py:83-90` 建议兜底非 `ValueError`/`TypeError` 异常并返回 500 JSON，同时保证发送 `tool` `ok: False` 事件。
- **私有目录权限与 Token 比较**：`copilot.py:107, 119` 确保 `private/workflow-harness`、`conversations` 及 `workflow.patch.yml`、`recent.json` 具备受限权限（`0o700`/`0o600`）；`dsh_tools.mjs:35` 可改用 `crypto.timingSafeEqual` 比对 Bearer Token。
- **拖拽后宽屏右侧留白**：`workbench.css:96` 可将 `body:has(.workflow-agent) .wf` 改为 `body:has(.workflow-agent:not([style])) .wf`，避免浮窗拖到左侧后右侧仍保留 382px 空白。
- **空步骤草稿保留 `default_topic`**：`api/workflows.py:89-91` 处理 `steps == []` 时保留 `default_topic`。
- **流式响应非 JSON 提示**：`web/src/api/client.ts:66` 包裹 `JSON.parse(line)`，对反代返回的非 JSON 内容输出友好中文错误。
- **文档与遗留原型**：
  - `docs/API.md` 需补充新增的 5 个 `/api/workflows/agent/*` 接口说明。
  - 确认父提交 `8789766` 引入的 `work/visualizations/video-node-workbench.html`（706 行）是否在合并前移除。

---

## 测试覆盖与主干对齐清单

1. **修复测试代理脆弱性**：`tests/test_web_api.py:71` 的 `requests.post(...)` 未禁用环境代理（与 `self.http.trust_env = False` 不一致），建议改用 `trust_env = False` 的临时 `Session` 或显式 `proxies={"http": None, "https": None}`。
2. **补齐单元测试**：
   - `agent_tools.py`：8 种编辑操作、`add_step`（含 `image_gen` `ref_sources`）、`_bad_sources`、`if_revision` 409、32 次调用上限、运行中只读保护、`NaN`/非法类型拒绝、`run_request` 失效。
   - `agent_bridge.py`：403 鉴权、请求体长度上限、非活跃轮次拒写、重复 `/ready`。
   - `agent_plugins.py` 与 `shot-timing/index.mjs`：安装/启停/卸载状态机、缺 `pnpm` 409、计时边界。
   - 浏览器测试：覆盖节点图选中、浮窗开关/编辑应用、插件面板。
3. **Rebase 到最新 `main`（`8cba4a7`）**：
   - 解决 `web/src/api/schema.d.ts`（重新运行 `npm run api:types`）与 `web/src/store/store.ts` 冲突。
   - 对齐 PR #5/#6 媒体编辑字段时注意语义区分：**只有 `video_from` 是上游步骤连线**（接入 `agent_tools.py` 的 `SOURCE_TYPES`/`_bad_sources` 与 `WorkflowBoard.tsx` 的 `upstream()`）；`video_round_id` 与 `last_frame_round_id` 是作品库编号、`video_task` 是用途枚举，沿用主干素材和用途校验，避免把作品编号误报成缺失节点。
