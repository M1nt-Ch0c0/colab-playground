# Workflow & Creative Harness 实施总纲（M1 → M2 → M3）

- **目标分支**：`feat/workflow-harness`（基于最新 `main@18328f5` + PR #11 `ad90c32`，已含 PR #5/#6 媒体编辑、PR #7 PR 规范、PR #8 CI、PR #9 GPU/主题修复、PR #10 工作流变量与画布位置、PR #11 项目改名 **ColabReel** 与 `colabreel.*` 存储键）
- **原分支保护**：`codex/workflow-harness-wip@ab6ac8e` 保持原样不动。
- **产品红线（硬边界）**：
  1. **Harness 只负责创作与界面操作，运维/基础设施工具全部不进 Harness**（不暴露 Colab 抢卡/释放/OAuth/HF Token、空闲超时、LLM 服务商密钥 CRUD/探测、代理线路 CRUD/切换、永久删除/批量空间清理）。
  2. **静态注入 26 个创作域工具**（取消日常 `studio_find_tools` 两跳发现），固定 `SYSTEM`（含 `ui-motion-spec.md` §4.5 语调段与范例）与工具 schema 顺序以命中 DeepSeek 前缀 KV Cache；所有 NDJSON `tool` 事件必须透传 `op` 字段（当参数含 `op` 时）以便前端通过 `toolLabel(name, op)` 渲染中文标签。
  3. **UI 与文案由 Claude 规格文件钉死**：所有前端可见中文文案、按钮、状态、错误码提示、动效参数与 CSS Token 必须严格遵守 `docs/harness/ui-motion-spec.md` 与 `web/src/features/workflow/agentCopy.ts`（杜绝防御性免责话术与小字暴露内部契约/PID）。
  4. **容器内插件可用**：`Dockerfile` 运行镜像补齐 `node + pnpm`；插件安装/卸载使用版本化 profile 目录，保证不踩坏运行中 `dsh` 进程的 `node_modules` 且不丢活跃插件内存。

---

## 一、模块与文件所有权划分

| 模块 | 路径 | 职责 |
|---|---|---|
| 错误码契约 | `draw_studio/workflows/harness_errors.py` | 统一结构化错误码 `HarnessError(code, status, detail)`，不向 UI 拼防御性长句 |
| 持久化状态层 | `draw_studio/workflows/harness_store.py` | `$QP_ROOT/private/workflow-harness/state.sqlite3`（WAL、`0o600`），承载 `shots`、`proposals`、`undo_records`、`masks`、`operations`、`operation_items`、`tool_telemetry` |
| 插件版本化管理 | `draw_studio/workflows/agent_plugins.py` | 版本化 profile 目录（`profiles/v-<id>/` + `active.json`）、离线安装/启停/卸载可信插件（`studio-shot-timing`） |
| 回环工具桥 | `draw_studio/workflows/agent_bridge.py` + `draw_studio/workflows/dsh_tools.mjs` | 私有 Token 回环通道、`/tool`（模型工具调用）、`/context`（插件只读内部上下文，不发 UI 工具事件不占额度）、`/stop` 三态协同（`cancelled` / `idle` / `unconfirmed`）、`timingSafeEqual` |
| 常驻会话池 | `draw_studio/workflows/copilot.py` | `HarnessSessions`（4 槽位 LRU、`forgetting` 墓碑、锁外 `dispose`/`rmtree`）、`_wait_turn` 严格状态机、代理环境变量签名与本机绕行、可配置 `contextWindow`/`maxTokens`/`max_tokens`、`recent.json` 容错、孤儿草稿目录 TTL 清理 |
| 静态创作工具集 | `draw_studio/workflows/agent_tools.py` | 26 个静态创作工具的 schema 定义、严格校验、上下文装配与领域服务调度 |
| HTTP 控制面 | `draw_studio/api/workflows.py`（可拆 `draw_studio/api/harness.py` 并挂载在 `/api/workflows/agent/*`） | 对话流、停止、会话历史、插件、逐镜查询/改写、提案采用/拒绝、撤销、蒙版句柄、操作账本审批/重试/取消、本地 Telemetry 摘要 |
| 前端文案硬字典 | `web/src/features/workflow/agentCopy.ts` | **由 Claude 定死**，唯一用户可见中文文案与错误码映射来源 |
| 前端画布与助手 UI | `web/src/features/workflow/{WorkflowBoard,WorkflowAgent,AgentPlugins,ProposalCard,OperationCard}.tsx` + `workbench.css` | 严格实现 `docs/harness/ui-motion-spec.md` 与 `agentCopy.ts`，接通工作流节点图、节点内 AI 改写、提案 Diff 卡、冲突恢复条、后台操作进度/部分重试卡、插件页 |
| 跨工作区联动 | `web/src/features/workflow/Workflow.tsx`、`web/src/store/store.ts`、`web/src/api/{client,types,schema.d.ts}`、`web/src/mock/server.ts` | 深链、表单/草稿同步、Mock 路由补齐、OpenAPI TypeScript 类型同步 |
| 容器与文档 | `Dockerfile`、`requirements.txt`、`docs/API.md` | 运行镜像补装 `node + pnpm`，更新 HTTP API 文档 |

---

## 二、结构化错误码契约（`harness_errors.py`）

后端返回给前端或工具层的错误必须带标准 `code`（HTTP 错误体格式：`{"error": "<简短回退文案>", "code": "<code>", "details": {...}}`；NDJSON `error` 事件格式：`{"type": "error", "code": "<code>", "message": "<简短回退文案>"}`）。前端优先按 `code` 查 `agentCopy.ts` 渲染自然中文：

- `invalid_argument`（400）
- `not_found`（404）
- `revision_conflict`（409，附 `current_revision`）
- `shot_conflict`（409，附 `conflicts[]`）
- `busy`（409，同会话已有进行中轮次或会话池全忙）
- `running_locked`（409，工作流正在运行，当前不可修改）
- `draft_already_saved`（409，草稿已保存为运行记录，附 `run_id`）
- `model_unconfigured`（400，未配置改写/对话模型）
- `model_error`（502，模型响应异常或未能完成本轮）
- `turn_stopped`（正常中止，用户取消本轮）
- `turn_timeout`（504，超时未完成）
- `plugin_unavailable`（409，缺 `pnpm` 或插件状态冲突）
- `approval_required`（409，需先在界面确认操作）
- `queue_full`（409，生成队列已满）
- `colab_unauthed`（400，尚未连接算力）
- `media_invalid`（400，素材不存在/尺寸或时长不符）
- `tool_limit_reached`（400，单轮工具调用达上限）
- `internal_error`（500）

---

## 三、26 个静态创作工具目录（固定启动注入，零运维工具）

所有工具在 `dsh` 启动时按固定顺序静态注册，不依赖两跳 `studio_find_tools`：

### A. 上下文与目录（2）
1. `studio_read_context` — 读取当前工作区（`workflow | image | video`）、活动运行/草稿、选中步骤/镜头、独立创作台草稿摘要、参考槽摘要与当前修订号。
2. `studio_get_catalog` — 按分区（`image | video | comfy | limits | nodes`）读取合法模型、视频模式、卸载模式与参数边界。

### B. 工作流、模板与运行（9）
3. `studio_list_templates` — 列出内置与自定义工作流模板摘要。
4. `studio_manage_template` — `op: "save" | "delete"`，保存或删除自定义模板（自动剔除运行专属 `asset_files`，保护内置模板）。
5. `studio_list_runs` — 列出工作流运行与草稿摘要（含进度、状态、成片 ID）。
6. `studio_create_draft` — 从模板或定义创建持久化草稿（支持 `request_id` 幂等）。
7. `studio_read_workflow` — 读取当前工作流主题、变量、步骤列表、选中步骤状态与有界产出摘要。
8. `studio_list_nodes` — 列出节点目录或查询单个 `step_type` 的配置字段与默认值。
9. `studio_edit_workflow` — 原子暂存 `operations[]`（`set_topic` / `rename_workflow` / `add_step` / `update_step` / `move_step` / `remove_step` / `set_variable` / `remove_variable`），完整支持 `video_from`、`video_round_id`、`video_task`、`last_frame_round_id`、`offload_mode`、`position` 与严格类型/范围校验。
10. `studio_validate_workflow` — 运行前干跑预检：上游连线（含 `video_from`）、缺失素材、未定义 `{{vars.*}}` 引用与受影响步骤。
11. `studio_manage_run_assets` — `op: "list" | "bind_rounds" | "remove"`，查询/绑定画廊作品编号到 `asset_input` 或移除运行素材。

### C. 逐镜读写、改写与执行控制（6）
12. `studio_read_shots` — 读取 `llm_script`（`scenes`）与 `h3_prompt`（`items`）的镜头列表，每镜含稳定 `shot_id`、`generation`、字段版本、关联关键帧/片段编号。
13. `studio_rewrite_prompt` — 调用 `Studio.write_prompt_rich` 为指定镜头（`keyframe_prompt` / `video_prompt`）或独立创作台提示词生成候选稿，落库为持久化 `proposal`（返回 `proposal_id`、`before`、`after`、`references_used`、`readset`、`writeset`），与节点内「AI 改写」按钮完全共用同一服务。
14. `studio_apply_shot_edits` — 按 `proposal_id` 或显式逐镜字段补丁写回镜头输出，支持 `atomicity: "all" | "per_shot"` 与字段级 CAS，返回 `applied`、`conflicts`、`undo_id`。
15. `studio_undo_change` — 按 `undo_id` 撤销最近一次字段写回（校验目标字段当前版本未再被修改）。
16. `studio_request_run` — 向界面提交启动/继续/单步重试运行请求（交付前按最终草稿复检目标步骤与启用状态，由用户在界面确认执行）。
17. `studio_watch_run` / `studio_cancel_run` — 查询运行进度与增量日志；停止指定运行（归并为 `studio_run_status`：`op: "watch" | "cancel"`，使总工具数精确控制在 **24 个**）。

### D. 作品库、参考图与媒体编辑（5）
18. `studio_find_assets` — 按 `query`、`kind`、`starred`、`offset`、`limit` 检索作品库，返回有界摘要。
19. `studio_inspect_asset` — 按 `round_id`（保留前导零）读取单件作品白名单元数据、尺寸/时长、来源关系与生成参数。
20. `studio_edit_media` — `op: "crop" | "extract_frame" | "clip_video"`，复用 `draw_studio.media` 执行裁图、取帧、裁段并返回新作品 `round_id`。
21. `studio_prepare_mask` — 校验并持久化局部重绘蒙版句柄 `mask_id`（`source_id` + 归一化笔迹），或返回打开画笔选区弹层的 UI 引导。
22. `studio_references` — `op: "read" | "use_round" | "remove" | "clear"`，读取/绑定/移除/清空首帧、尾帧、视频参考与有序参考图（保持白模动作人设图顺序语义）。

### E. 作品整理、预设、独立生成与任务队列（3，其中作品整理与预设合并为清晰域工具）
23. `studio_library_actions` — `op: "star" | "trash" | "list_trash" | "restore"`，仅包含界面级收藏、移入回收站、查看回收站与恢复（**严禁永久清除**）。
24. `studio_presets` — `op: "list" | "save" | "delete" | "parse_comfy_link"`，管理 `studio` 与 `comfy` 参数预设及解析 Comfy 模型链接。
25. `studio_generation` — `op: "edit_composer" | "prepare" | "submit_image" | "submit_video"`：
    - `edit_composer`：向前端独立创作台提交参数修改提案（由前端应用到 Zustand `draft`）；
    - `prepare`：调用 `normalize_job` 做参数归一化与输入校验；
    - `submit_image` / `submit_video`：冻结参考图/尾帧/视频/蒙版快照，按 `idempotency_key` 创建 `awaiting_approval` 状态的 `Operation`，返回 `operation_id` 供用户在界面一键确认入队（避免模型未经确认直接扣卡）。
26. `studio_jobs` — `op: "list" | "read" | "cancel" | "retry"`，查看队列/单条任务/操作账本进度，按精确 `job_id` 取消排队或运行中任务（在 `Studio._lock` 内校验目标 `job_id`），按冻结快照重试失败任务。

> 注：连同上面拆分共 **26 个静态创作工具**（都在 20–30 黄金区间内），零运维工具；外加按需安装的可信插件（如 `studio_shot_timing`）。

---

## 四、SQLite 持久层 Schema（`harness_store.py`）

文件位于 `$QP_ROOT/private/workflow-harness/state.sqlite3`（父目录 `0o700`，文件 `0o600`，`PRAGMA journal_mode=WAL`）：

1. **`shots`**：`(run_id, step_id, shot_id PRIMARY KEY, generation INTEGER, seq INTEGER, title TEXT, fields_json TEXT, field_versions_json TEXT, updated_at INTEGER)`
   - 读取/同步规则：每次从 `WorkflowEngine` 读取 `llm_script` 的 `scenes[]` 或 `h3_prompt` 的 `items[]` 时，为缺少 `shot_id` 的条目分配稳定 `sh_<hex12>` 并写回输出；当步骤重跑导致输出整批替换时递增 `generation` 并重置 `field_versions`，使旧提案自动失效（返回 `shot_conflict`）。
2. **`proposals`**：`(proposal_id PRIMARY KEY, scope_key TEXT, kind TEXT, run_id TEXT, step_id TEXT, target_json TEXT, readset_json TEXT, writeset_json TEXT, before_json TEXT, after_json TEXT, refs_json TEXT, model TEXT, status TEXT, undo_id TEXT, created_at INTEGER, expires_at INTEGER)`
3. **`undo_records`**：`(undo_id PRIMARY KEY, scope_key TEXT, run_id TEXT, step_id TEXT, inverse_json TEXT, expected_versions_json TEXT, consumed INTEGER DEFAULT 0, created_at INTEGER)`
4. **`masks`**：`(mask_id PRIMARY KEY, source_id TEXT, strokes_json TEXT, created_at INTEGER, expires_at INTEGER)`
5. **`operations`**：`(operation_id PRIMARY KEY, scope_key TEXT, tool TEXT, idempotency_key TEXT, spec_hash TEXT, state TEXT, spec_json TEXT, frozen_refs_json TEXT, executor_ids_json TEXT, result_json TEXT, error_code TEXT, error_detail TEXT, created_at INTEGER, updated_at INTEGER)` + `UNIQUE(scope_key, tool, idempotency_key)`
6. **`operation_items`**：`(operation_id TEXT, item_key TEXT, seq INTEGER, frozen_input_json TEXT, job_id TEXT, state TEXT, round_id TEXT, error TEXT, updated_at INTEGER, PRIMARY KEY(operation_id, item_key))`
7. **`tool_telemetry`**：`(id INTEGER PRIMARY KEY AUTOINCREMENT, turn_id TEXT, conversation_key TEXT, call_seq INTEGER, model TEXT, tool_name TEXT, op TEXT, ok INTEGER, error_code TEXT, retry_in_turn INTEGER, latency_ms INTEGER, cache_hit_tokens INTEGER, cache_miss_tokens INTEGER, proposal_outcome TEXT, created_at INTEGER)`
   - 脱敏保证：绝不存 `api_key`、`token`、`cookie`、完整用户提示词或媒体二进制；随 `Runtime` 定期清理超过 30 天或超出 20,000 条的旧记录。

---

## 五、分里程碑实施与验收清单

### Milestone 1（基础重构、Review P0/P1 全清、主干对齐与 Docker `node+pnpm`）
- [ ] 将 `copilot.py`、`agent_bridge.py`、`agent_tools.py`、`agent_plugins.py`、`dsh_tools.mjs`、`plugins/shot-timing/`、`WorkflowBoard.tsx`、`WorkflowAgent.tsx`、`AgentPlugins.tsx`、`workbench.css` 干净集成到 `main@18328f5` 上（保留 `main` 的全部媒体编辑、变量与轮询逻辑，不引入 `work/visualizations/`）。
- [ ] 清零 `docs/harness/review.md` 全部 P0/P1：
  - `add_step` 过滤继承的默认 `ref_sources`/`extra_ref_sources`（显式传入非法引用继续报错）；支持 `video_from` 连线（区分 `video_round_id`/`last_frame_round_id`/`video_task`）；严格数值/有限浮点/列表元素校验；编辑后复检失效 `run_request`。
  - `_wait_turn` 严格校验 `admitted` / 错误 `idle`；`/stop` 两端三态协同（`204` cancelled / `200 {"state":"idle"}` / `409` unconfirmed）；`native-session` 损坏保留 `.corrupt.<ts>` 备份再回退。
  - `HarnessSessions` 引入 `forgetting` 集合、锁外 `dispose`/`rmtree`、`finally` 必 `notify_all()`。
  - `agent_plugins.py` 实现**版本化 profile 目录**（`profiles/v-<ts>-<hex>/` + 原子指针 `active.json`），活跃 `dsh` 进程继续锚定原目录，不丢插件内存也不被 `pnpm` 踩坏。
  - `copilot.py` 将代理环境变量纳入 `_profile_signature()`，本机/私网 `urlsplit(provider.base).hostname` 绕过出口代理；三处模型预算（`contextWindow` / `maxTokens` / `max_tokens`）可配置且默认放宽（如 128k / 8192 / 4096）；`recent.json` 损坏容错；孤儿草稿对话目录 TTL 清理；`emit()` 捕获 `RuntimeError`；私有目录/文件权限 `0o700`/`0o600`。
  - `agent_bridge.py` 新增 `/context` 只读端点供 `shot-timing` 调用（消除幻影「读取工作流」徽章与额度消耗）；转发全部插件工具事件；`dsh_tools.mjs` 用 `crypto.timingSafeEqual`；非预期异常返回 500 JSON。
  - `Dockerfile` 运行镜像安装 `node`（从 build 阶段拷贝或装官方二进制）与 `pnpm`，并在 `requirements.txt` 保持 `deepseek-harness-sdk==0.2.2rc2`。
  - 前端按 Claude 的 `ui-motion-spec.md` 与 `agentCopy.ts` 彻底清除 GPT 味与小字暴露（移除 `dsh PID` / `dsh · 已启动` 等）、修复历史合并顺序、`tryTiming` 保留输入框草稿、Portal 联动禁用、草稿上传失败刷新侧栏、`workbench.css` 拖拽留白修复、`mock/server.ts` 补齐路由。
  - 单元测试全覆盖：`tests/test_harness_tools.py`、`tests/test_harness_runtime.py`、`tests/test_web_api.py`（修复 `trust_env = False`）。

### Milestone 2（静态创作工具包、逐镜 `shot_id` + 字段 CAS、共享提案卡与 Telemetry）
- [ ] 实现 `harness_store.py`（`shots`、`proposals`、`undo_records`、`tool_telemetry`）。
- [ ] `agent_tools.py` 扩展工作流/模板/运行/逐镜/改写/采用/撤销/作品查询工具并静态注册；重写 `SYSTEM` 为自然简洁中文 + 3–5 条高频范例 + 收窄「每轮先读工作流」规则。
- [ ] 开放提案与逐镜 HTTP 路由，使浮窗与节点内「AI 改写」按钮共用同一 `rewrite_prompt` → `proposal` → `apply_shot_edits`（CAS）→ `undo` 服务；开放 `GET /api/workflows/agent/telemetry` 脱敏聚合接口。
- [ ] 前端按 Claude 规格实现共享的 `ProposalCard`（Diff + 参考图缩略图 + 采用/放弃/撤销）、`ConflictBar`（冲突提示 + 重新生成/保留现稿）以及节点内 `llm_script`/`h3_prompt` 逐镜「AI 改写」入口。
- [ ] 补齐 M2 单元测试与 API 契约测试（并发改不同镜合并成功、同镜冲突返回 `shot_conflict`、撤销成功与过期撤销拒绝、Telemetry 聚合验证）。

### Milestone 3（媒体编辑工具、生成操作账本、跨工作区适配与 Chrome CDP 采图）
- [ ] 扩展 `harness_store.py` 增加 `masks`、`operations`、`operation_items` 表。
- [ ] 实现剩余静态创作工具：`studio_edit_media`、`studio_prepare_mask`、`studio_references`、`studio_library_actions`、`studio_presets`、`studio_generation`、`studio_jobs`（`Studio._lock` 内校验 `job_id` 精准取消）。
- [ ] 开放 `/api/workflows/agent/operations*` 与 `/api/workflows/agent/masks` 接口，实现带 `idempotency_key` 与冻结素材快照的操作审批、状态回读（跨刷新/断连恢复）与失败项局部重试。
- [ ] 前端按 Claude 规格实现 `OperationCard`（确认执行、进度展示、部分失败单项重试）、Composer 补丁应用与 MediaEditor 蒙版句柄同步。
- [ ] 更新 `docs/API.md`，运行 `npm run api:types`、`npm run api:check`、`npm run build`，跑通全套 Python 单测/API 测/工作流测/浏览器测。
- [ ] 编写并运行非交互 Chrome (`--headless=new`) + CDP 验证与截图采帧脚本，输出桌面 `1440px` / 窄屏 `390px` × 浅色 / 深色 × 浮窗收起/展开/对话/提案 Diff/冲突态/操作进度/插件页的静态截图与动效过程帧，供 Claude 与我联合终验。
