# Studio 给 dsh 的工具目录

本目录以 `origin/main@61ccfcd` 为能力事实，以 `codex/workflow-harness-wip@16ae892` 为集成原型。应用 OpenAPI 有 74 个路径、93 个操作。下面的 77 个名字是完整的能力归属与覆盖率账本。**最终产品边界明确：Harness 只负责画布/工作台内的创作与界面操作，不接入算力抢释、密钥/代理管理、永久删除/批量清理等运维工具。** 面向模型的创作能力静态归并为 26 个工具一次性注册，详见 [实施总纲](./implementation-plan.md) · [总体设计](./overview.md) · [详细设计](./detailed-design.md#工具静态注入粗粒度归并与模型预算)

## 怎么读这张表

每个名字对应一个可独立授权、显示和测试的创作或管理动作。参数列列出业务字段，共用的身份证明、版本、幂等键和响应信封见详细设计。`op`、`mode` 和 `scope` 采用有限枚举。实现时为每个变体生成独立参数约束。

| 标记 | 依据 |
|---|---|
| 原 / 插件 | 分支已有 dsh 工具或可装插件。行内点明现有实现和目标的差距。 |
| 接 | 主干已有直接服务或 HTTP 操作，主要工作是适配类型、范围、错误与返回体。 |
| 补 | 部分能力已存在，还需补作用域、版本、幂等、任务或交互契约。 |
| 新 | 当前主干缺少对应持久对象或命令，需要引擎或宿主开发。 |
| 低 / 中 / 高 | 低表示单服务薄适配。中涉及多状态或外部依赖。高涉及跨域一致性、持久对象、不可逆副作用或执行边界。 |
| P0–P3 | P0 打通创作上下文与核心编排，P1 接入真实媒体与生成，P2 完成受控运维及批处理，P3 扩展时间线内核。优先级与可行性相互独立。 |

“读”直接返回最小投影。“写”绑定对象版本。“推理”和“外部读”标明外部调用及必要时的费用。“执行”和“破坏”使用具体资源和副作用授权。“宿主”可让 Agent 发起交接，文件选择、秘密输入与最终受控动作在对应界面完成。

## 上下文和能力发现

| 工具 | 用户动作 | 关键输入 → 输出 | 作用 / 排期 | 实现基础、难度和缺口 |
|---|---|---|---|---|
| `studio_find_tools` | 查询已装插件与扩展能力 | query, domain?, cursor → name、summary、schema_rev、下一页 | 发现 / P2 | 新·中。日常创作工具改为启动静态注入，本能力降级为多插件场景下的可选目录查询，不再作为调用内置能力的前置步骤。 |
| `studio_read_context` | 定位工作对象 | view_ref? → draft/run、节点、镜头、素材句柄、revision、选择来源 | 读 / P0 | 补·高。主干的当前镜头、选区、播放器时间在浏览器。断线时使用最后确认的对象 ID。 |
| `studio_get_catalog` | 查询模型及合法参数 | section=image/video/comfy/gpu/limits → 枚举、默认值、参数界限 | 读 / P0 | 接·低。从 config 投影请求的分区，模型名称和限制随服务器变化。 |
| `studio_read_status` | 查看运行状态和增量日志 | scope, log_since?, limit → phase、当前任务、有限日志、next_seq | 读 / P0 | 接·中。聚合状态含全局线路与账号信息，需按权限裁剪、脱敏。 |
| `studio_read_storage` | 查询占用和回收站容量 | 无 → 作品/回收站数量与大小、可用字节 | 读 / P1 | 接·低。复用 Store.storage_stats。 |

## 工作流、节点和逐镜 AI

| 工具 | 用户动作 | 关键输入 → 输出 | 作用 / 排期 | 实现基础、难度和缺口 |
|---|---|---|---|---|
| `studio_list_templates` | 浏览可复用流程 | query?, origin?, cursor → template_id、名称、步骤摘要 | 读 / P0 | 接·低。拆出内置与自定义模板，分页摘要。 |
| `studio_save_template` | 另存或更新模板 | source_draft, name, overwrite_id?, base_revision → template_id、revision | 写 / P0 | 补·中。主干按 ID 或同名替换。显式区分新建、覆盖并剔除运行专属上传文件。 |
| `studio_delete_template` | 删除用户模板 | template_id, base_revision → removed | 破坏 / P2 | 接·低。复用内置保护，展示被删模板名。 |
| `studio_list_runs` | 浏览草稿与运行 | project?, status?, cursor → run_id、进度、成片 ID | 读 / P0 | 接·低。主干是实例列表，项目隔离待补。 |
| `studio_create_draft` | 从模板或定义创建持久草稿 | request_id, template_id 或 workflow, topic → run_id、草稿版本 | 写 / P0 | 接·低。已有带 request_id 的 create_run，创建与开始运行可分开。 |
| `studio_read_workflow` | 读活动草稿与选中节点 | 当前 scope → topic、steps、variables、selected_step、状态 | 读 / P0 | 原·中。分支支持当前编辑器及暂存修改。扩大前需限定返回字段和大输出分页。 |
| `studio_list_nodes` | 查询节点及默认配置 | step_type? → 可用节点或单类参数表 | 读 / P0 | 原·低。目录来自 STEP_CATALOG，端口类型和互斥条件需要补充。 |
| `studio_edit_workflow` | 改图、变量或节点配置 | operations[], base_revision → proposal_id、字段差异/新版本 | 写 / P0 | 原·高。分支已经支持批量暂存。目标增加服务端提交、变量引用校验及主干 video_from 端口。 |
| `studio_validate_workflow` | 运行前检查 | draft_id, until_node? → 缺失输入、非法边、未解析变量、受影响节点 | 读 / P0 | 补·中。复用 normalize_workflow_def，同时区分原有默认值与用户明确绑定的引用。 |
| `studio_suggest_step` | 在任意选中节点调用 AI | node_id, instruction, field_mask → 候选字段、依据、输入版本 | 推理 / P1 | 新·中。七类节点各有可建议字段。现有 call_llm 可用，采用走编辑命令。 |
| `studio_read_shots` | 按镜头读脚本与产物 | run_id, node_id, shot_ids?, fields?, cursor → shot、提示词、帧/片段句柄 | 读 / P0 | 补·高。现有 scenes/items 属于步骤输出，需稳定 shot_id 和生成版本。 |
| `studio_rewrite_prompt` | 复用原有生图、视频、逐镜改写 | target, text/instruction, mode, refs[], provider?, model? → 候选 prompt、model、images_used、input_digest | 推理 / P0 | 补·高。已有 write_prompt_rich。必须解析本镜真实关键帧、用途和变量，逐镜输出写回独立。 |
| `studio_apply_shot_edits` | 采用一镜或多镜的候选稿 | proposal_id, shot_ids[], expected_versions → applied、conflicts、undo_id | 写 / P1 | 新·高。主干更新整个 output 列表。需在锁内改目标字段，保留其他镜头的并发编辑。 |
| `studio_request_run` | 启动、继续、单步或从某步执行 | mode, run_id, step_id?, expected_revision → action_id，授权后 run_id/status | 执行 / P0 | 原·高。当前工具只提交请求，工作台按钮实际执行。后台执行、授权及重试去重待补。 |
| `studio_watch_run` | 查询单次运行的进度 | run_id, after_cursor?, include_outputs? → 步骤状态、日志、产物、下一游标 | 读 / P0 | 补·中。主干可轮询整条记录，目标增加有界增量与事件续读。 |
| `studio_cancel_run` | 停止指定运行 | run_id, expected_status → cancel_requested 或终态 | 执行 / P1 | 接·中。只取消指定运行，区分已请求和已退出。 |
| `studio_delete_run` | 删除指定记录及所属上传 | run_id, revision → removed、保留的作品编号 | 破坏 / P2 | 接·中。运行中已有冲突保护。分支还须释放该记录的 dsh 和私有对话目录。 |
| `studio_manage_run_assets` | 列出、绑定、移除运行素材 | op, run_id, step_id, upload_id/round_id/asset_handle → 有序素材及版本 | 读/写 / P1 | 补·中。二进制上传与画廊编号走不同代码路径。移除会影响具体节点引用。 |
| `studio_undo_change` | 撤销已应用的字段变更 | undo_id, expected_revision → 新版本或字段冲突 | 写 / P1 | 新·高。需要字段级逆操作和版本链。计算消耗、永久删除没有对应逆操作。 |
| `studio_shot_timing` | 估算剪辑前片长 | 当前选中节点和连接 → 分镜数、帧数、fps、预计秒数 | 插件读 / P0 | 插件·低。可安装示例按 H3 的 24 fps 计算。多视频分支、裁段与转场需独立时间线计算。 |

## 素材库、参考输入与媒体编辑

| 工具 | 用户动作 | 关键输入 → 输出 | 作用 / 排期 | 实现基础、难度和缺口 |
|---|---|---|---|---|
| `studio_find_assets` | 搜索作品 | query?, kind?, starred?, sort?, cursor?, limit → round_id 和有界摘要 | 读 / P0 | 原·低。当前返回最多 8 件，主干 Store.list 可扩充分页和收藏条件。 |
| `studio_inspect_asset` | 查元数据和来源 | round_id, fields? → mime、尺寸、时长、生成来源及可用操作 | 读 / P0 | 接·中。采用元数据白名单，截断长 prompt，保留 RID 字符串前导零。 |
| `studio_open_media` | 查看原图、缩略图、下载或当前画面 | asset_ref, variant, disposition → resource_handle 或宿主预览动作 | 读/宿主 / P1 | 补·中。主干支持认证媒体和 Range。图像视觉输入由宿主显式适配，视频内容不能靠下载链接推断。 |
| `studio_compare_assets` | 对照两个或多次生成结果 | round_ids[], fields, visual? → 元数据差异、预览句柄 | 读 / P2 | 补·中。主干可在客户端比较。自动视觉判断另需模型能力和可追溯证据。 |
| `studio_import_asset` | 导入用户选定文件 | upload_id, kind, name? → round_id、尺寸、时长 | 宿主写 / P1 | 补·中。主干接收原始字节，先由浏览器上传并产生限域句柄。 |
| `studio_crop_image` | 裁出角色或局部 | source_round_id, x, y, width, height → 新图片 round_id | 写 / P1 | 接·低。使用原图像素坐标，图形选区由宿主提供，复用 image_crop。 |
| `studio_extract_frame` | 取首帧、指定时间帧、尾帧 | video_id, position, time_s? → 新图片 round_id | 写 / P1 | 接·低。时间从播放器选择或显式指定，由 FFmpeg 读取。 |
| `studio_clip_video` | 裁段、可选静音 | video_id, start_s, end_s, mute → 新视频 round_id | 写 / P1 | 接·中。验证真实媒体时长。长任务需后台 operation_id 和超时。 |
| `studio_prepare_mask` | 准备局部重绘选区 | source_round_id, mask_handle 或 request_brush → mask_id、预览、source_revision | 宿主写 / P1 | 补·高。已有笔刷和 MaskedEdit。服务端选区句柄、过期机制以及自动分割是不同工作。 |
| `studio_read_references` | 读输入参考与顺序 | target → 首/尾帧、有序图像、视频、来源 ID | 读 / P0 | 补·中。主干 refs_report 是共享槽。工作流/镜头的显式引用需单独解析。 |
| `studio_set_references` | 绑定、替换、追加、移除、清空参考 | target, op, slot, asset_ref, expected_revision → 引用版本及角色 | 写 / P1 | 补·高。motion 首张角色图可单独替换并保留其余输入。任务使用独立快照，隔离跨标签页共享槽。 |
| `studio_star_assets` | 收藏或取消收藏 | round_ids[], starred → updated[] | 写 / P1 | 接·低。单件和批量都已有，设置绝对值可重试。 |
| `studio_trash_assets` | 将作品移入回收站 | round_ids[], expected_revision → deleted[]、可恢复状态 | 破坏 / P1 | 接·中。先展示数量和引用影响。永久删除对应独立能力。 |
| `studio_list_trash` | 浏览回收站 | query?, cursor → round_id、过期信息、预览句柄 | 读 / P2 | 接·低。主干返回列表，工具增加分页。 |
| `studio_restore_assets` | 恢复回收站作品 | round_ids[] → restored[]、missing[] | 写 / P2 | 接·低。沿用已有恢复与缺失反馈。 |
| `studio_plan_cleanup` | 预览按空间或日期清理 | criteria, kind?, include_starred? → plan_id、matched_ids、bytes | 读 / P2 | 接·低。主干支持 dry_run。记录匹配集合及条件。 |
| `studio_apply_cleanup` | 执行已预览清理 | plan_id, approval_id? → deleted[]、bytes 或 conflict | 破坏 / P2 | 补·中。把 matched 原样提交为 expected_ids，候选变更须重算预览。 |
| `studio_purge_assets` | 永久删除已选内容或清空回收站 | source, exact_ids/preview_all, approval_id → purged[]、bytes | 破坏 / P2 | 补·高。区分现有作品与回收站，显式展示全量范围和不可恢复性。 |

## 生成、队列和预设

| 工具 | 用户动作 | 关键输入 → 输出 | 作用 / 排期 | 实现基础、难度和缺口 |
|---|---|---|---|---|
| `studio_edit_composer` | 修改独立生图/视频草稿 | composer_id, operations, revision → 参数差异及新版本 | 写 / P1 | 新·高。主干的表单和部分选择在 Zustand/本地。需宿主快照或服务端草稿。 |
| `studio_prepare_generation` | 归一化参数和估算影响 | mode, draft/shot, refs, params → normalized_spec、任务数、费用不确定项、input_digest | 读 / P1 | 补·中。复用 normalize_job 和目录限制。缺少可靠 CU 价格时返回 unknown。 |
| `studio_generate_image` | 生图、参考改图或局部重绘 | spec_ref 或 prompt+params, refs[], mask_id?, idempotency_key → job_ids[] | 执行 / P1 | 补·高。复用 Diffusers/Comfy 与 mask 合成。需快照与计费提交幂等。 |
| `studio_generate_video` | 文生视频、首尾帧及参考视频生成 | mode, video_task?, frame_refs, video_ref?, ordered_images, params, idempotency_key → job_ids[] | 执行 / P1 | 补·高。区分编辑、续拍、白模动作、人设图角色。需冻结帧数和媒体来源。 |
| `studio_list_jobs` | 查询运行中、排队和历史任务 | status?, cursor → job_id、状态、阶段、输出 ID | 读 / P1 | 接·低。复用队列概览，过滤私有参数。 |
| `studio_read_job` | 查看一个任务及失败诊断 | job_id, after_seq? → 状态、进度、retryable、结果/错误 | 读 / P1 | 补·中。主干有 find_job 和公共队列，尚无按 ID 的专用 GET。 |
| `studio_cancel_job` | 针对一条任务取消 | job_id, expected_state → removed 或 interrupt_requested | 执行 / P1 | 补·高。排队取消已有 ID。正在运行的 stop 只指向全局 current，需锁内校验目标。 |
| `studio_retry_job` | 按已冻结参数重试 | job_id, idempotency_key → new_job_id、retried_from | 执行 / P1 | 补·中。复用主干 retry_job 的来源快照和已有重试语义。 |
| `studio_clear_queue` | 批量移除排队任务 | preview 或 exact_job_ids, approval_id? → removed、冲突项 | 破坏 / P2 | 补·高。主干 clear 作用于整个队列，须绑定预览集。当前运行单独处置。 |
| `studio_list_presets` | 列出 Studio/Comfy 预设 | family, query? → preset_id、参数摘要 | 读 / P1 | 接·低。区分内置、自定义及模板类型。 |
| `studio_save_preset` | 创建或更新预设 | family, spec, overwrite_id? → preset_id、revision | 写 / P1 | 接·中。复用现有校验，覆盖需目标明确。 |
| `studio_delete_preset` | 删除自定义预设 | family, preset_id → removed | 破坏 / P2 | 接·低。沿用内置保护。 |
| `studio_parse_comfy_link` | 解析模型链接 | url → 规范模型 spec | 读 / P1 | 接·低。仅接受现有解析器认可的链接格式。 |
| `studio_list_loras` | 查仓库可选 LoRA 文件 | repo_id → 有界 files[] | 外部读 / P1 | 接·中。Hugging Face 超时及私有仓权限须反馈。 |
| `studio_recent_models` | 管理最近模型 | op=list/add/remove, model? → 有序列表 | 读/写 / P2 | 接·低。列表只是偏好，区别于当前生成模型或激活改写模型。 |

## 算力、模型、出站线路和凭据交接

| 工具 | 用户动作 | 关键输入 → 输出 | 作用 / 排期 | 实现基础、难度和缺口 |
|---|---|---|---|---|
| `studio_compute_status` | 查 Colab 授权和算力 | detail? → 已授权、GPU、余额可见性、活动会话数 | 读 / P1 | 接·中。优先缓存摘要，显式刷新可阻塞访问上游。过滤账号标识。 |
| `studio_acquire_gpu` | 预占算力 | gpu_pool[], poll_rounds, proxy_policy, approval_id → operation_id/状态 | 执行 / P2 | 补·高。主干返回 202 并启动线程，需持久操作 ID、并发保护与费用说明。 |
| `studio_release_gpu` | 释放运行时 | expected_runtime, affected_jobs, approval_id → operation_id、实际释放结果 | 破坏 / P2 | 补·高。release_all 同时清队列、打断当前任务并释放运行时，应展示完整影响。 |
| `studio_set_idle_timeout` | 设置空闲释放时间 | minutes, previous? → 实际生效值 | 管理 / P2 | 接·低。用主干限制与全局作用域。 |
| `studio_list_providers` | 读可用模型服务商 | capability?, purpose? → provider_id、协议、模型、key_set、active | 读 / P0 | 接·低。仅提供脱敏元数据。 |
| `studio_refresh_models` | 同步一个服务商模型目录 | provider_id → 模型列表和版本 | 外部读 / P2 | 接·中。沿用 provider revision 校验，处理慢上游。 |
| `studio_test_provider` | 探测模型 | provider_id, model? → ok、时延、脱敏错误 | 外部读 / P2 | 接·中。发送小型测试请求，可能产生调用费。 |
| `studio_select_model` | 选择本次或全局模型 | scope=turn/project/studio, provider_id, model → effective_selection | 写/管理 / P1 | 补·中。主干全局 active 已有，单次改写可显式覆盖。项目级选择待持久化。 |
| `studio_manage_provider` | 管理服务商配置 | op, provider_id?, nonsecret_patch? → settings_handoff 或脱敏状态 | 宿主管理 / P2 | 补·高。修改 base URL 会改变数据目的地。密钥仅在设置页录入与保存。 |
| `studio_list_proxies` | 查看线路配置 | 无 → 脱敏 ID、标签、当前线路 | 读 / P2 | 接·低。复用 masked/hint 白名单。 |
| `studio_test_proxy` | 测试指定线路 | profile_id → ok、时延、粗粒度位置或错误 | 外部读 / P2 | 接·中。仅测已保存线路，裁剪输出。 |
| `studio_select_proxy` | 切换已保存线路 | profile_id 或 system, expected_active → 生效状态 | 管理 / P2 | 接·中。作用于 Studio 全局，需显示影响。 |
| `studio_manage_proxy` | 增删改线路配置 | op, id?, label? → settings_handoff 或配置版本 | 宿主管理 / P2 | 补·中。含认证的 URL 在受控表单中处理。 |
| `studio_open_settings` | 打开人工登录、授权和密钥设置 | task=studio_login/colab_connect/colab_disconnect/hf_token/provider_secret/proxy_secret → handoff_id、完成/取消状态 | 宿主 / P0 | 补·中。模型只收到状态。OAuth code、token、密码及登录 Cookie 由宿主传递。 |

## Harness 运维与进阶编排

| 工具 | 用户动作 | 关键输入 → 输出 | 作用 / 排期 | 实现基础、难度和缺口 |
|---|---|---|---|---|
| `studio_list_plugins` | 查看插件与工具来源 | scope → 包版本、工具名、安装/启用状态、所需能力 | 读 / P0 | 补·中。分支浮窗已有展示接口，通用插件依赖和模型侧查询需目录化。 |
| `studio_change_plugin` | 提出安装、启停、卸载请求 | action, package_ref, version?, approval_id? → 操作状态、是否需重载 | 宿主管理 / P2 | 补·高。分支能离线安装一个可信包。任意来源安装涉及服务端代码执行。 |
| `studio_session_status` | 诊断、查看会话和进程 | conversation_ref → 生命周期、能力版本、恢复原因 | 读 / P1 | 补·中。宿主已有会话事件和停止控制。停止当前对话走宿主带 turn_id 的通道。 |
| `studio_edit_timeline` | 修改镜头排列、入出点、转场 | timeline_id, operations[], revision → 新剪辑清单和受影响片段 | 写 / P3 | 新·高。主干提供裁段和拼片，持久 EDL、多轨语义、镜头级版本待建。 |
| `studio_render_cut` | 按编辑决定清单输出成片 | timeline/step, preset, revision, idempotency_key → operation_id、final_round_id | 执行 / P3 | 补·高。简单序列可复用 video_stitch。任意轨道、变速和精确音频混合另需渲染器。 |

## 主干 HTTP 对照

直接从指定修订运行 `create_app().openapi()` 得到下表。每个已发布的 method/path 单列，兼容别名也计数。工具可以调用同一领域服务。传输行说明宿主实际执行的那一段。主干的 REST 平面和目标 dsh 工具平面各有独立版本。[路由组装](https://github.com/M1nt-Ch0c0/colab-playground/blob/61ccfcd3d1dd3c6a4fa9acc794f56cf87a1453fa/draw_studio/application.py) · [主干 API 文档](https://github.com/M1nt-Ch0c0/colab-playground/blob/61ccfcd3d1dd3c6a4fa9acc794f56cf87a1453fa/docs/API.md)

### 宿主

| 主干操作 | 目标工具或宿主 | 映射说明 |
|---|---|---|
| `GET /healthz` | `studio_read_status` | 可用性与 busy 摘要 |
| `POST /api/login` | 浏览器会话 | Studio 登录，密码由浏览器提交 |
| `POST /api/logout` | 浏览器会话 | 退出登录并清 Cookie |

### 工作台与算力

| 主干操作 | 目标工具或宿主 | 映射说明 |
|---|---|---|
| `GET /api/config` | `studio_get_catalog` | 按域返回能力、默认值和限制 |
| `GET /api/status` | `studio_read_status` | log_since 游标，另为上下文提供状态 |
| `GET /api/presets` | `studio_list_presets` | Studio 预设 |
| `POST /api/presets` | `studio_save_preset` | Studio 预设 |
| `DELETE /api/presets/{preset_id}` | `studio_delete_preset` | Studio 预设 |
| `GET /api/models/recent` | `studio_recent_models` | list |
| `POST /api/models/recent` | `studio_recent_models` | add |
| `DELETE /api/models/recent` | `studio_recent_models` | remove |
| `POST /api/settings` | `studio_set_idle_timeout` | 全局空闲释放分钟数 |
| `POST /api/generate` | `studio_generate_image`、`studio_generate_video` | 同一提交入口，两类参数契约 |
| `GET /api/queue` | `studio_list_jobs`、`studio_read_job` | 后台队列公开投影 |
| `POST /api/queue/clear` | `studio_clear_queue` | 现有动作清空排队任务 |
| `POST /api/queue/{job_id}/retry` | `studio_retry_job` | 已提交任务的重试 |
| `POST /api/queue/{job_id}/cancel` | `studio_cancel_job` | 排队任务，兼容写法 |
| `DELETE /api/queue/{job_id}` | `studio_cancel_job` | 排队任务 |
| `POST /api/stop` | `studio_cancel_job`、`studio_clear_queue` | 全局当前任务，可同时清队列 |
| `POST /api/release` | `studio_release_gpu` | 释放全部运行时并影响队列 |
| `POST /api/comfy/parse-link` | `studio_parse_comfy_link` | 返回模型 spec |
| `GET /api/comfy/presets` | `studio_list_presets` | Comfy 预设 |
| `POST /api/comfy/presets` | `studio_save_preset` | Comfy 预设 |
| `DELETE /api/comfy/presets/{preset_id}` | `studio_delete_preset` | Comfy 预设 |
| `POST /api/hf/list-loras` | `studio_list_loras` | 查询 safetensors 文件名 |
| `GET /api/colab/status` | `studio_compute_status` | 显式刷新 Colab 状态 |
| `POST /api/colab/auth/start` | `studio_open_settings` | 宿主启动 OAuth |
| `POST /api/colab/auth/complete` | `studio_open_settings` | 宿主提交授权码，成功后恢复队列 |
| `POST /api/colab/auth/logout` | `studio_open_settings` | 宿主断开账号 |
| `POST /api/colab/grab` | `studio_acquire_gpu` | 202 抢卡 |
| `POST /api/colab/hf-token` | `studio_open_settings` | 宿主保存或清空 HF token |

### 改写模型

| 主干操作 | 目标工具或宿主 | 映射说明 |
|---|---|---|
| `GET /api/llm` | `studio_list_providers` | 读取脱敏服务商和 active |
| `POST /api/llm/providers` | `studio_manage_provider` | 创建/更新，秘密字段经宿主 |
| `DELETE /api/llm/providers/{provider_id}` | `studio_manage_provider` | 删除特定服务商 |
| `POST /api/llm/providers/{provider_id}/models` | `studio_refresh_models` | 拉取模型列表 |
| `POST /api/llm/providers/{provider_id}/test` | `studio_test_provider` | 原生协议探测 |
| `POST /api/llm/active` | `studio_select_model` | 全局激活选择 |
| `POST /api/prompt` | `studio_rewrite_prompt` | 独立面板已接入，逐镜需上下文适配 |

### 出口线路

| 主干操作 | 目标工具或宿主 | 映射说明 |
|---|---|---|
| `GET /api/proxy` | `studio_list_proxies` | 脱敏线路列表 |
| `POST /api/proxy` | `studio_select_proxy`、`studio_manage_proxy` | 选择线路。旧 custom_url 经宿主 |
| `POST /api/proxy/profiles` | `studio_manage_proxy` | 创建/更新线路 |
| `DELETE /api/proxy/profiles/{profile_id}` | `studio_manage_proxy` | 删除线路 |
| `POST /api/proxy/test` | `studio_test_proxy` | 测试已保存线路 |

### 作品库与参考图

| 主干操作 | 目标工具或宿主 | 映射说明 |
|---|---|---|
| `GET /api/storage` | `studio_read_storage` | 作品、回收站和磁盘 |
| `GET /api/rounds` | `studio_find_assets` | 作品筛选与分页 |
| `POST /api/rounds/import` | `studio_import_asset` | 宿主上传图片或 MP4 |
| `POST /api/rounds/{rid}/crop` | `studio_crop_image` | 原图像素裁切 |
| `POST /api/rounds/{rid}/frame` | `studio_extract_frame` | 首/尾/指定秒 |
| `POST /api/rounds/{rid}/clip` | `studio_clip_video` | 时间区间和静音 |
| `POST /api/rounds/delete` | `studio_trash_assets`、`studio_purge_assets` | 软删与 permanent 分权 |
| `POST /api/rounds/star` | `studio_star_assets` | 批量收藏 |
| `POST /api/rounds/cleanup` | `studio_plan_cleanup`、`studio_apply_cleanup` | 先预览，执行时核对 expected_ids |
| `GET /api/rounds/{rid}` | `studio_open_media` | 宿主取媒体，download 可选 |
| `DELETE /api/rounds/{rid}` | `studio_trash_assets`、`studio_purge_assets` | 单件 |
| `GET /api/rounds/{rid}/thumb` | `studio_open_media` | 宿主取缩略图 |
| `GET /api/rounds/{rid}/meta` | `studio_inspect_asset` | 元数据投影 |
| `POST /api/rounds/{rid}/delete` | `studio_trash_assets`、`studio_purge_assets` | 兼容写法 |
| `PATCH /api/rounds/{rid}/star` | `studio_star_assets` | 单件 |
| `POST /api/rounds/{rid}/star` | `studio_star_assets` | 兼容写法 |
| `POST /api/rounds/{rid}/use` | `studio_set_references` | 作品放入首/尾或视频槽 |
| `GET /api/trash` | `studio_list_trash` | 回收站列表 |
| `POST /api/trash/restore` | `studio_restore_assets` | 按 ID 恢复 |
| `POST /api/trash/purge` | `studio_purge_assets` | 指定项或全部 |
| `GET /api/trash/{rid}/thumb` | `studio_open_media` | 回收站预览 |
| `GET /api/trash/{rid}` | `studio_open_media` | 回收站预览原件 |
| `GET /api/video-reference` | `studio_read_references`、`studio_open_media` | 视频槽句柄与二进制预览 |
| `POST /api/video-reference` | `studio_set_references` | 从宿主上传 MP4 |
| `DELETE /api/video-reference` | `studio_set_references` | 按当前视频参考 ID 清除 |
| `GET /api/last-frame` | `studio_read_references`、`studio_open_media` | 独立尾帧 |
| `DELETE /api/last-frame` | `studio_set_references` | 清除尾帧 |
| `POST /api/last-frame` | `studio_set_references` | 上传尾帧 |
| `GET /api/reference` | `studio_read_references`、`studio_open_media` | 图片参考或单件预览 |
| `DELETE /api/reference` | `studio_set_references` | 清槽或按 ID 移除 |
| `POST /api/reference` | `studio_set_references` | 替换、按 ID 替换或追加 |
| `POST /api/use-latest-image` | `studio_set_references` | 最新图片绑首帧 |
| `GET /api/image` | `studio_open_media` | 最新图片兼容入口 |

### 工作流

| 主干操作 | 目标工具或宿主 | 映射说明 |
|---|---|---|
| `GET /api/workflows` | `studio_list_templates`、`studio_list_nodes`、`studio_list_runs` | 模板、目录、运行摘要聚合 |
| `POST /api/workflows` | `studio_save_template` | 创建或更新自定义模板 |
| `GET /api/workflows/runs` | `studio_list_runs` | 运行摘要 |
| `POST /api/workflows/runs` | `studio_create_draft` | 接受 request_id |
| `GET /api/workflows/runs/{run_id}` | `studio_read_workflow`、`studio_watch_run`、`studio_read_shots` | 当前定义、步骤状态及产物 |
| `PATCH /api/workflows/runs/{run_id}` | `studio_edit_workflow` | 非运行态修改 topic/workflow |
| `DELETE /api/workflows/runs/{run_id}` | `studio_delete_run` | 删除记录及其上传文件 |
| `POST /api/workflows/runs/{run_id}/resume` | `studio_request_run` | 继续执行 |
| `POST /api/workflows/runs/{run_id}/start` | `studio_request_run` | 支持 from_step_id、single_step、draft_only |
| `POST /api/workflows/runs/{run_id}/cancel` | `studio_cancel_run` | 取消指定运行 |
| `POST /api/workflows/runs/{run_id}/steps/{step_id}/retry` | `studio_request_run` | 单步或从此往后 |
| `PATCH /api/workflows/runs/{run_id}/steps/{step_id}/output` | `studio_apply_shot_edits` | 现有实现合并输出字段，尚缺逐镜 CAS |
| `POST /api/workflows/runs/{run_id}/steps/{step_id}/output` | `studio_apply_shot_edits` | 兼容写法 |
| `POST /api/workflows/runs/{run_id}/assets` | `studio_manage_run_assets` | 上传运行专属图片 |
| `GET /api/workflows/runs/{run_id}/assets/{filename}` | `studio_manage_run_assets`、`studio_open_media` | 原图或 thumb |
| `DELETE /api/workflows/runs/{run_id}/assets/{filename}` | `studio_manage_run_assets` | 移除本次上传 |
| `DELETE /api/workflows/{workflow_id}` | `studio_delete_template` | 删除自定义模板 |

### 传输与纯前端能力

- OpenAPI 统计以文档中的操作为分母。`GET /api/openapi.json`、`GET /`、`GET /legacy`、`GET/POST /login`、`GET /logout`、静态 `/assets` 及为可读路由实现的 `HEAD` 归宿主和传输层。原图、缩略图、Range 和下载使用同源认证，由资源句柄定位。
- 画布拖拽、缩放、当前选区、比较面板、画笔、播放器播放头、系统文件选择器和保存文件属于浏览器交互。持久坐标交给图编辑，画笔与播放头变为带原件版本的选区或时间点。纯视口位置由该标签页管理。
- 主干已经支持的七类可执行步骤为 `asset_input`、`llm_script`、`web_asset_fetch`、`image_gen`、`h3_prompt`、`video_gen`、`video_stitch`。它们通过图配置和运行工具组合。网页找图沿用引擎已有的 URL 限制、筛选及下载边界。
- 分支新增的 `POST /api/workflows/agent/turn`、`GET /api/workflows/agent/plugins`、`POST /api/workflows/agent/plugins/{package}`、`GET /api/workflows/agent/conversations/{key}`、`POST /api/workflows/agent/conversations/{key}/stop` 属于浮窗控制面，单独验证。终止某轮对话、取消 GPU 作业、取消工作流是三个不同的请求目标。
- Agent 插件原生注册的工具独立编目。每个外部包在安装时登记包名、版本、工具描述、所需宿主服务及权限。后来安装的扩展按该协议加入目录，不预先假定其工具和效果。
