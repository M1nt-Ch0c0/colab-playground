# ColabReel 后端设计与运行说明

ColabReel 使用 Python、FastAPI 和 Uvicorn。React 和 API 由同一个服务在 8787 端口提供。一个数据卷对应一个执行进程。作品、队列和工作流沿用各自的磁盘格式，模型服务商配置使用 Python 自带的 SQLite。

## 代码与状态归属

以下路径相对于后端包 `draw_studio/`。根目录的 `app.py` 提供命令行和 ASGI 入口。

| 模块 | 负责的状态和操作 |
|---|---|
| `application.py`、`runtime.py` | 应用工厂装配路由。进入运行生命周期时取得数据卷锁、加载凭据、恢复队列并启动清理线程，退出时保存状态。 |
| `api/` | HTTP 层处理 Cookie / Bearer 鉴权、登录限流、请求大小、错误格式和媒体响应。路由调用领域服务，提交生成任务和启动工作流均返回 202。 |
| `generation/` | `catalog.py` 提供模型、预设与限制，`parameters.py` 校验请求并解析模型链接，`studio.py` 管理生成队列、参考图快照和空闲释放。H3 指南随包放在 `h3/references/`。 |
| `colab/` | `client.py` 在宿主机申请 GPU、访问 Jupyter 和传输文件。`worker.py` 作为独立脚本上传至远端 `/content/colab_worker.py`，连续任务复用同一内核。 |
| `workflows/` | `definitions.py` 定义步骤目录和模板，`engine.py` 负责运行、人工审核与恢复。`web_assets.py` 负责网页素材获取，`video.py` 负责本地拼接。生成步骤向同一个 `Studio` 队列提交自己的参考图。 |
| `gallery.py`、`llm.py` | `Store` 管理作品文件和回收站。模型服务商模块负责 SQLite 事务和原生协议请求，`api/llm.py` 定义允许对外返回的字段。 |

### 七项前后端差距

| 项目 | 实现及验收入口 |
|---|---|
| G1 多服务商改写 | 设置中添加、编辑、测试服务商，拉取或手填模型。创作台下拉框选择模型，图像改写、分镜、候选图筛选、H3 提示词共用选择器。 |
| G2 静态页面 | `GET /` 公开提供 `web/dist/index.html`，HTML 使用 `no-store`，`/assets/` 下的指纹资源可缓存一年。静态目录限定在构建产物内。受保护的旧页面可通过 `/legacy` 访问。 |
| G3 JSON 会话 | 首页请求受保护配置得到 401 后显示 `#login`。React 调用 `POST /api/login` 和 `POST /api/logout`。表单登录与 JSON 登录共享每 IP、10 分钟 8 次失败的限额。 |
| G4 暂停可见 | `GET /api/status` 的 `workflow_active` 优先显示执行中的实例，然后显示最近更新的暂停实例。顶栏显示“待审核”和完成步数。单独的待审核实例允许部署时通过空闲检查。 |
| G5 改写凭据 | 服务商、密钥和模型选择使用设置页或认证 API 管理。全新数据卷从空列表开始。 |
| G6 素材缩略图 | 工作流素材格和网页选图结果请求原地址加 `?thumb=1`。服务端首次读取时生成最长边 480px 的 JPEG，返回私有缓存和 ETag。旧运行的图片也可按需生成。 |
| G7 草稿素材 | 选模板、改步骤和选本地图都留在浏览器。点运行后创建草稿记录、上传图片，全部成功才启动。上传失败可移除有问题的文件，直接重试同一份草稿。 |

实际联调还修正了两处响应字段。参数预设保存和删除都返回 `custom` 列表，React、旧页面和演示模式读取同一字段。工作流素材上传返回 `{ok, filename, asset, assets}`，服务端负责把文件挂到步骤上。页面重新读取已保存的步骤，避免延迟写回旧的素材列表。生图参数预设支持保存和套用 Diffusers 模型或 ComfyUI 三件套。

## 会话与 HTTP 契约

成功登录返回 `200 {"ok":true}`，同时设置 `qp_auth`，属性为 `HttpOnly`、`Secure`、`SameSite=Lax`、`Path=/` 和 30 天有效期。密码错误返回 401，超限返回 429。退出清除浏览器 Cookie。脚本使用原有的 Bearer token。反向代理部署采用 HTTPS，若由代理转发客户端 IP，Uvicorn 的 `FORWARDED_ALLOW_IPS` 应指向实际可信的入口代理。

JSON API 的错误对象为 `{"error":"中文说明"}`。输入错误返回 400，资源不存在返回 404，状态冲突返回 409。HTTP 请求体上限为 16 MiB，工作流图片限 PNG、JPEG、WebP 且每张至多 12 MiB。作品下载支持 HEAD、ETag、Range 和附件下载。客户端请求用相对地址，反向代理挂在子路径时，请从带结尾斜杠的入口访问并转发剥离前缀后的路径。

登录后访问 `GET /api/openapi.json` 可读取运行版本的契约。前端的会话、改写输入输出与服务商类型由该文档生成。变更 Python 模型后，在装好项目依赖的虚拟环境执行 `npm --prefix web run api:types`。CI 通过 `npm --prefix web run api:check` 检查生成文件。作品库、队列、参考图等已有接口见 [HTTP API](API.md)。

## 改写模型

| 方法与路径 | 输入 | 成功响应 |
|---|---|---|
| GET `/api/llm` | — | `{providers, active}` |
| POST `/api/llm/providers` | `{id?, kind, name, base_url, api_key?, models?, enhanced_rewrite?}` | 完整状态。省略 id 创建，指定 id 更新。 |
| DELETE `/api/llm/providers/{id}` | — | 删除后的完整状态 |
| POST `/api/llm/providers/{id}/models` | `{}` | 拉取完成后的完整状态 |
| POST `/api/llm/providers/{id}/test` | `{model?}` | `{ok, ms, model, error}`。发起一次真实短对话，服务商拒绝或超时会得到 `ok:false`。 |
| POST `/api/llm/active` | `{provider_id, model}` | 完整状态 |
| POST `/api/prompt` | 原改写参数，可加 `provider_id` 与 `model` | `{prompt, model, format, images_used}` |

服务商对象包含 `id, kind, name, base_url, key_set, key_masked, models, models_fetched_at, enhanced_rewrite, legacy_template`，拉取时间为 Unix 秒或 null。新增需要 Key，更新时空 Key 保留原值。省略 `models` 保留现有列表，传 `[]` 表示清空。当前选择始终指向一个有 Key 且有该模型的服务商。删除或清空当前模型后，按添加顺序选择第一家可用服务商的第一个模型，全部为空则返回 `active:null`。

增强改写按服务商保存，`enhanced_rewrite` 默认关闭。启用后，创作台和 H3 改写会额外描述画面细节并约束输出格式，上游拒绝仍作为错误返回。已使用旧版破甲模板的数据库记录在升级时保留原选择，`legacy_template` 是只读标记。关闭时使用标准模板，同一服务商可重新选用原有模板。更改协议或地址后使用通用增强模式。

单次改写可同时指定服务商与模型，这只影响该请求。省略两者会在开始调用时读取当前选择，未配置返回 400。服务端从参考图槽位、最新作品或工作流的镜头素材获取图片，保留首尾帧和多图顺序。工作流每次调用时读取当前选择，审核期间切换模型会作用于后续调用。

| 协议 | 对话地址、鉴权、图片格式 | 模型列表 |
|---|---|---|
| OpenAI 兼容 | BASE 已含网关前缀和所需的 `/v1`，追加 `/chat/completions`。Bearer 鉴权，发送 `messages` 与 `image_url`。 | `/models` 的 `data[].id` |
| Anthropic | BASE 追加 `/v1/messages`。用 `x-api-key` 与版本头发送顶层 `system`、`max_tokens` 和 base64 image block。 | `/v1/models`，用 `after_id` 翻页 |
| Gemini | BASE 追加 `/v1beta/models/{model}:generateContent`。用 `x-goog-api-key` 发送 `systemInstruction`、`contents` 和 `inlineData`。 | `/v1beta/models`，跟随 `nextPageToken`，只保留支持 `generateContent` 的模型，去掉 `models/` 前缀。 |

本机和内网网关沿用直连策略，公网请求使用服务配置的出站环境。请求带超时，携带 Key 的请求禁止跟随重定向。上游错误只返回状态或可操作的错误说明。模型列表翻页全部成功才提交，拉取期间配置被修改会返回 409。上游认证失败在改写接口返回 502，浏览器会话继续有效。

## 工作流步骤参数

- 生图和视频步骤的 `gpu_pool` 按尝试顺序排列，`gpu` 等于第一项。切换首选 GPU 会重置为单卡，之后可按顺序添加候补卡。读取旧记录时，若下拉值与原封未动的内置默认池冲突，采用下拉选择。显式自定义池保留其顺序。
- `poll_all_proxies` 和 `auto_offload` 使用 JSON 布尔值。旧记录中的字符串 `"false"` 按关闭处理。视频步骤指定 `offload_mode` 时以该模式为准。
- 拼接转场使用 `cut` 或 `fade`，旧表单的 `none` 按硬切读取。淡化模式下片段过短时，FFmpeg 拼接器仍会回退到硬切。

## 持久化、重试和升级

- 服务商、密钥和当前选择一起保存在 `$QP_ROOT/private/llm.sqlite3`。私有目录创建权限 0700，文件权限 0600。SQLite 事务同时提交模型列表与当前选择，网络请求在事务外执行。升级时保留现有服务商 ID、密钥与当前选择。只在旧环境文件中填过网关的用户，需在设置页添加一次服务商。
- 出口线路和当前选择原子写入权限 0600 的 `$QP_ROOT/private/proxies.json`。第一次启动会读取已配的 `proxy_url`、`proxy_url_<id>`、旧自定义代理文件和队列里的线路选择。之后以设置页保存的数据为准，删除后重启也会保留这次删除。
- 已排队的生成任务和参考图快照仍保存在 `out/queue.json` 和 `out/queue_refs/`。启动时恢复排队任务，有 Colab 凭据即可继续消费。重启时正在执行的单个生成任务记为中断。工作流则保留已完成步骤，将中断步骤改回待执行，用户点击继续后从该步骤重新开始。浏览器刷新只重新读取这些状态。
- 运行中的摘要直接读取当前实例。暂停摘要在保存运行记录时更新，在启动恢复时重建。高频状态轮询只访问当前记录和内存中的暂停摘要。
- 草稿每次创建携带稳定的 32 位小写十六进制 `request_id`。重试相同请求返回同一实例。按步骤与图片内容生成素材文件名，重传会复用文件。首次启动带 `draft_only:true`，服务端在工作流锁内检查状态，防止重复启动。草稿中的 File 在当前页面内暂存。已上传的文件属于运行实例，删除素材或实例会清理相应缩略图。
- Docker 构建阶段用 Node 22 编译生产前端，最终 Python 3.13 镜像携带静态文件、远端执行脚本、H3 指南和 FFmpeg。Uvicorn 使用一个 worker，每个进程在启动恢复前独占数据卷的 `.studio.lock`。部署采用一个副本，先停旧进程再启动新镜像。
- 发布沿用标签触发 GitHub Actions、Artifact Registry 和 Dokploy 的流程。`/healthz` 保留 `busy, queue_len, workflow_running`，抢卡和释放期间也会报告忙碌。回退时在 Dokploy 选回上一个镜像并继续挂载原数据卷。私有模型和代理配置随数据卷保留。镜像目标与部署变量见 [自动发布说明](deployment.md#github-自动发布维护者)。

## 本地验证

在项目根目录、已激活的 Python 虚拟环境运行以下命令。真实视频拼接用到 FFmpeg 和 ffprobe，浏览器用例用到 Chromium / Chrome、配套驱动和 Selenium。测试创建临时数据卷并连接本地模型协议服务器。

```bash
npm --prefix web ci
npm --prefix web run api:check
npm --prefix web run build
python -c 'import subprocess; from draw_studio import legacy_ui as ui; subprocess.run(["node", "--check"], input=ui._JS.encode(), check=True)'
python tests/test_backend_v21.py .
python tests/test_comfy_mode.py .
python tests/test_workflows.py .
python tests/test_web_api.py .
python -m pip install selenium
python tests/test_web_browser.py .
```

浏览器用例从未登录的首页开始，覆盖密码报错、设置服务商、拉模型、改写、生图工作台切换至工作流、草稿批量选图、上传失败后重试、缩略图加载、审核继续和退出。
