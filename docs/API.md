# Colab Studio（colab-playground）HTTP 接口文档

服务地址：`https://your-domain.example.com`（服务器本机是 `http://127.0.0.1:8787`）

当前服务的机器可读契约为 `GET /api/openapi.json`（需要登录）。工作流素材上传、缩略图、草稿重试和全部改写服务商接口见[后端设计与运行说明](backend-redesign.md)。

---

## 1. 通用约定

| 项目 | 说明 |
|---|---|
| 认证 | 二选一：① 浏览器 Cookie `qp_auth`（`POST /login` 拿到）；② 请求头 `Authorization: Bearer <token>`，token 就是 `secret.env` 里的 `token`（和 Cookie 的值一样） |
| 请求体 | 除上传图片外都是 JSON，要带 `Content-Type: application/json` |
| 成功 | `200`，异步任务返回 `202`，媒体缓存命中返回 `304` |
| 失败 | 统一返回 `{"error": "中文说明"}`。常见状态码：`400` 参数错误，`401` 没登录，`404` 不存在，`409` 冲突（比如队列满了），`413` 请求体超过 16MB，`416` Range 无效，`429` 登录失败次数太多，`502` 模型服务商或 Hugging Face 请求失败 |
| 作品编号 | `id` 是 3–7 位数字字符串，比如 `"007"`。编号只增不减，删掉的编号**不会再用**，所以媒体地址可以长期缓存 |
| 时间 | 都是 Unix 秒 |

```bash
# 后面的例子都用这两个变量
B=https://your-domain.example.com
H="Authorization: Bearer $QP_TOKEN"
```

---

## 2. 网页入口、登录和健康检查

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/healthz` | `{"ok":true,"backend":"colab","version":"3.1","busy":false,"queue_len":0,"workflow_running":false}` |
| GET | `/login` | 登录页 |
| POST | `/login` | 表单 `password=...`。成功返回 `302`，并下发 `qp_auth` Cookie（30 天）。同一 IP 10 分钟内失败 8 次后返回 `429` |
| GET | `/logout` | 清掉 Cookie，跳回登录页 |
| GET | `/` | React 工作台，浏览器收到 API 的 401 后显示 `#login` |
| POST | `/api/login` | JSON `{"password":"…"}`，成功设置 Cookie 并返回 `{"ok":true}`。认证失败 401，限流 429。 |
| POST | `/api/logout` | 已登录时清除 Cookie，返回 `{"ok":true}` |
| GET | `/legacy` | 旧工作台，需要登录 |

---

## 3. 配置、状态和存储

### `GET /api/config`

返回可选项和参数范围。客户端应该按这里的值生成界面，不要写死。

```json
{
  "version": "3.1",
  "gpus": [{"id":"A100","label":"A100 · High-RAM","vram":40,"hint":"推荐，性价比最高"}],
  "image_models": [{"id":"qwen-2.1-bf16"},{"id":"qwen-2.1-q5"},{"id":"flux2-dev"}],
  "recent_models": ["black-forest-labs/FLUX.1-dev", "qwen-2.1-bf16"],
  "video_workflows": [{"id":"t2va","needs":[]},{"id":"fl2va","needs":["first"]},{"id":"ref2va","needs":["first"]}],
  "comfy": {
    "templates": [{"id":"qwen-image-2.1","label":"...","clip_type":"qwen_image","defaults":{...}}, {"id":"flux"}, {"id":"sd-generic"}],
    "samplers": ["euler","er_sde","dpmpp_2m","..."],
    "schedulers": ["simple","normal","karras","..."],
    "clip_types": ["qwen_image","flux","stable_diffusion","..."],
    "builtin_presets": [{"id":"builtin:omni-bf16-35","name":"Omni BF16 · 35步精细", ...}],
    "presets": []
  },
  "limits": {"size_min":512,"size_max":1536,"size_step":64,"steps_min":2,"steps_max":60,
             "cfg_min":1.0,"cfg_max":12.0,"frames_min":120,"frames_max":360,"count_max":4,
             "loras_max":4,"lora_scale_max":2.5,"idle_minutes_min":5,"idle_minutes_max":60,
             "prompt_max":12000,"negative_max":1200,"upload_max_mb":12,"queue_max":12},
  "defaults": {"image":{},"video":{},"gpu":"A100","idle_minutes":10},
  "trash_retention_days": 7
}
```

### `GET /api/status?log_since=<seq>`

轮询用的总状态。`log_since` 填上一次返回的 `log_seq`，这样只拿新增的日志。

| 字段 | 说明 |
|---|---|
| `phase` | `idle` / `starting` / `ready` / `generating` / `stopping` / `error` |
| `error` | `phase=error` 时的错误信息 |
| `error_id` | 本次失败的唯一标识，同一次失败在轮询中保持一致。其他状态为 null。 |
| `active_gpu` | 当前占用的 Colab GPU，比如 `"A100 (HIGH_RAM)"` |
| `idle_minutes`, `idle_deadline` | 空闲自动释放的分钟数（`0` 为永不超期），以及预计释放的时间点（没在倒计时或永不超期就是 `null`） |
| `current` | 正在跑的任务（结构见 [任务对象](#任务对象)），没有就是 `null` |
| `queue` | 排队中的任务数组（持久化在 `out/queue.json`，服务重启后自动恢复） |
| `history` | 最近 10 个已结束的任务（持久化在 `out/queue.json`） |
| `logs`, `log_seq` | 新增日志行、最新日志序号 |
| `gallery_rev` | 作品库版本号。每次增删、收藏都会变，变了再去拉 `/api/rounds` |
| `latest` | 最新一个作品（[作品对象](#作品对象)） |
| `references` | `{"first":{set,bytes,source,updated_at},"last":{...}}`。`source` 取值：`upload`，`round:<id>`，`legacy` |
| `recent_models` | 最近使用/保存的生图模型列表（最多 16 个，持久化在 `out/queue.json`） |
| `comfy_presets` | 用户保存的 ComfyUI 三件套组合方案列表（最多 32 个，持久化在 `out/queue.json`） |
| `proxy` | 当前出站代理状态：`active`（线路 ID，空字符串表示系统网络）、`profiles[]`（脱敏列表，不回显凭据）、`last_test` |
| `colab` | Colab 账号状态：`authed, ok, email, balance, rate_per_hour, sessions[], any_running, eligible_gpus[], eligible_tpus[], gpu_health{}, hf_token_set, refreshing, error`（后台异步刷新，不阻塞轮询；`gpu_health` 记录 30 分钟内各 GPU 最近一次分配实测结果 `ok/unavailable/error`） |
| `workflow_active` | 当前运行实例的摘要，或最近更新的暂停实例，均无时为 null。带 `status, done_steps, total_steps`。 |
| `server_time` | 服务器时间 |

### `GET /api/storage`

返回作品库、回收站和服务器磁盘剩余空间统计：

```json
{
  "rounds": {"count": 6, "images": 6, "videos": 0, "starred": 0, "bytes": 6120000},
  "trash": {"count": 0, "bytes": 0, "retention_days": 7},
  "total_bytes": 6120000,
  "disk_free_bytes": 25000000000,
  "disk_total_bytes": 50000000000
}
```

### `GET / POST / DELETE /api/models/recent`

管理「最近使用」生图模型列表（提交生图任务时也会自动写入队头，最多保留 16 个）：

- `GET /api/models/recent` → `{"recent_models": ["owner/repo", ...]}`
- `POST /api/models/recent` body `{"model": "owner/repo"}` → 校验并置顶保存，返回 `{"ok": true, "recent_models": [...]}`
- `DELETE /api/models/recent` body `{"model": "owner/repo"}`（或 `?model=...`）→ 移除该项，返回 `{"ok": true, "recent_models": [...]}`

### `GET / POST / DELETE /api/comfy/presets` 与 `POST /api/comfy/parse-link`

管理 ComfyUI 三件套组合方案与解析 Hugging Face 文件链接：

- `POST /api/comfy/parse-link` body `{"url": "https://huggingface.co/.../blob/main/...safetensors"}` → 返回 `{"ok": true, "spec": {source, repo_id, filename, revision, url, basename, ext, format}}`（支持 HF 网页链接、`resolve` 链接、`owner/repo :: path/file` 或直链）
- `GET /api/comfy/presets` → `{"presets": [...], "builtin_presets": [...]}`
- `POST /api/comfy/presets` body `{"name": "Omni BF16 + Turbo 8步", "template": "qwen-image-2.1", "diffusion": "...", "text_encoder": "...", "vae": "...", "sampler": "euler", "scheduler": "simple", "steps": 8, "cfg": 1.0, "width": 1024, "height": 1536, "loras": [...]}` → 返回 `{"ok": true, "preset": {...}, "presets": [...]}`
- `DELETE /api/comfy/presets/<id>` → 删除自定义组合方案，返回 `{"ok": true, "presets": [...]}`

### 出口代理线路

| 方法与路径 | 请求与返回 |
|---|---|
| GET `/api/proxy` | 返回 `{active, profiles, last_test}`，每条线路包含 `id, label, configured, masked, hint`。接口只返回脱敏地址。 |
| POST `/api/proxy/profiles` | `{"label":"主线路","url":"socks5://proxy.example:1080"}`，返回完整状态。带 `id` 则更新，编辑时地址留空或省略会保留原地址及凭据。 |
| DELETE `/api/proxy/profiles/{id}` | 删除线路并返回完整状态。删除当前线路后选择剩余的第一条，列表清空时恢复系统网络。 |
| POST `/api/proxy` | `{"active":"<线路 ID>"}` 选用已保存的线路，`{"active":""}` 使用系统网络。旧版请求体的 `custom_url` 仍可更新单条自定义线路。 |
| POST `/api/proxy/test` | `{"profile":"<线路 ID>"}`，省略时测试当前线路。返回 `{profile, ok, loc, colo, ms, at, error}`。 |

首次保存的线路自动启用。线路地址和当前选择保存在 `private/proxies.json`，权限 0600。使用系统网络时沿用进程的代理环境变量。模型请求访问本机及内网网关时直连。

### `POST /api/settings`

```json
{"idle_minutes": 20}
```
范围 5–60，会持久化到 `out/queue.json`。`0` 表示永不超期（保持持有，直到手动释放）。如果正在倒计时，会马上按新值重新计时；设为 `0` 会取消倒计时。返回 `{"ok":true,"idle_minutes":20}` 或 `{"ok":true,"idle_minutes":0}`。

### `POST /api/colab/grab`

在设置里抢一张卡并持有，不提交生图/生视频任务。需要已经完成 Colab 授权。

```json
{"gpu_pool": ["A100", "H100"], "poll_rounds": 2, "poll_all_proxies": false}
```

异步执行，看 `phase` 从 `starting` 变成 `ready`。已有任务或正在抢卡时返回 `409`。

---

## 4. 生成

### `POST /api/prompt`：使用所选模型改写提示词

```json
{"text": "雨夜霓虹街头，回头微笑", "mode": "image", "editing": false}
```
- `mode`：`image` 或 `video`
- `editing`：`true` 表示这是改已有图片的指令
- 可选的 `provider_id` 和 `model` 成对指定，省略时使用当前选择。返回 `{prompt, model, format, images_used}`。未配置模型返回 400，上游失败返回 502。

### `POST /api/generate`：提交任务（进持久化队列，异步执行）

公共字段：

| 字段 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `mode` | string | `image` | `image` 或 `video` |
| `prompt` | string | 必填 | ≤ 12000 字 |
| `negative` | string | `""` | 负面提示词，≤ 1200 字 |
| `gpu` | string | `A100` | `A100` / `H100` / `G4` / `L4` / `T4` |
| `gpu_pool` | array | `[gpu]` | 指定轮询的 GPU 列表（按顺序优先，如 `["G4","H100"]`） |
| `poll_rounds` | int | 1 | 轮询轮数（1–10） |
| `poll_all_proxies` | bool | false | `true` 时每轮依次切换全部已配置的代理 |
| `auto_fallback` | bool | false | 兼容旧版：`gpu_pool` 仅 1 张卡且为 `true` 时自动顺延尝试其余有权限的 GPU |
| `width`, `height` | int | 看模式 | 512–1536，会自动对齐到 64 的倍数 |
| `steps` | int | 图 35 / 视频 30 | 2–60 |
| `cfg` | number | 5.0 | 1–12 |
| `seed` | int | `-1` | `-1` 或不填表示随机；支持 `0`。实际用的种子会写进作品元数据 |
| `count` | int | 1 | 1–4，一次排几个任务，种子依次加 1 |
| `loras` | array | `[]` | 最多 4 个 `{"repo_id":"owner/repo","weight_name":"x.safetensors","scale":1.0}`，`scale` 范围 0–2.5 |
| `has_image` | bool | false | 是否用当前参考图（见第 6 节） |
| `idle_minutes` | int | - | 可选，顺便改空闲释放时间（5–60，或 `0` 永不超期，持久化） |
| `idea` | string | - | 可选，原始想法，只用来记录 |

生图（`mode=image`）专用：

| 字段 | 说明 |
|---|---|
| `engine` | `diffusers`（默认，整机模式）或 `comfyui`（三件套单文件模式） |
| `model` | `engine=diffusers` 时使用：`qwen-2.1-bf16`（默认）/ `qwen-2.1-q5` / `flux2-dev`，或任意 Hugging Face Diffusers 仓库 ID（`owner/repo`） |
| `comfy` | `engine=comfyui` 时必填：`{"template": "qwen-image-2.1"\|"flux"\|"sd-generic", "diffusion": "<链接>", "text_encoder": "<链接>", "vae": "<链接>", "sampler": "euler", "scheduler": "simple", "denoise": 1.0}`（支持 `.safetensors` / `NVFP4` / `FP8` / `.gguf`） |
| `chain` | `true` 时自动用**任务开始那一刻**最新的图片作品当参考图（“接着改”）。会覆盖 `has_image` |
| `custom_transformer_repo`, `custom_transformer_file` | 只有 `engine=diffusers` 且 `qwen-2.1-q5` 用，自定义 GGUF |

生视频（`mode=video`，MiniMax-H3）专用：

| 字段 | 说明 |
|---|---|
| `workflow` | `t2va`（文生视频）/ `fl2va`（首帧或首尾帧）/ `ref2va`（参考图）。后两个会自动把 `has_image` 设为 true |
| `num_frames` | 120–360，24 fps（5–15 秒，自动对齐 `17*n+5`）。124 帧约 5 秒 |
| `auto_offload` | 默认 true，开启 CPU offload |
| `has_last_image` | 只有 `fl2va` 有效，用当前设置的尾帧 |

参考图在**提交的那一刻**会被拷进任务并写入 `out/queue_refs/` 快照。之后再换参考图或重启服务，都不会影响已经在排队的任务。

返回 `202`：
```json
{"ok": true, "jobs": [ {"id": "j12345007", "status": "queued"} ]}
```
失败：`400`（参数错、没授权 Colab、需要参考图但没设置），`409`（队列满，最多 12 个）。

### 任务对象

```json
{
  "id": "j12345007", "status": "queued|running|done|error|canceled",
  "mode": "image", "model": "qwen-2.1-bf16", "workflow": null, "gpu": "A100",
  "width": 1024, "height": 1024, "steps": 30, "seed": 1234567,
  "prompt": "前 160 字…", "created_at": 0, "started_at": 0, "finished_at": 0,
  "stage": "queued|provisioning|uploading|generating|downloading|done",
  "progress": {"label": "", "pct": 45, "detail": "16/35", "rate": "00:10<00:12, 1.52it/s"},
  "round_id": "007", "error": ""
}
```
`progress` 来自 Colab 端 tqdm 进度条（已处理 ANSI 转义与 `\r` 实时刷新），可能是 `null`。

### 队列和运行时

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/queue` | `{"current":…, "queue":[…], "history":[…]}` |
| DELETE | `/api/queue/<job_id>` | 把排队中的任务移出队列（也可以用 `POST /api/queue/<job_id>/cancel`）。已经在跑的任务返回 `404`，要用 `/api/stop` |
| POST | `/api/queue/clear` | 清空队列，返回 `{"ok":true,"removed":N}` |
| POST | `/api/stop` | 取消当前任务。body `{"clear_queue": true}` 会同时清空队列 |
| POST | `/api/release` | 马上释放所有 Colab 运行时（停止消耗 CU），同时清空队列。异步执行，看 `phase` 变化 |

---

## 5. 作品库

### 作品对象

```json
{
  "id": "007", "kind": "image|video", "prompt": "…", "model": "qwen-2.1-bf16",
  "created_at": 0, "bytes": 1218890, "starred": false, "has_thumb": true, "mtime": 0,
  "negative": "…", "workflow": null, "gpu": "A100", "width": 1024, "height": 1024,
  "steps": 30, "cfg": 5.0, "seed": 1234567, "num_frames": null, "loras": [],
  "has_image": false, "chain": false, "duration_s": 74.2, "job_id": "j12345007", "idea": "…"
}
```
旧图片作品即使 `.json` 里没写尺寸，也会自动从图片头读取 `width` 和 `height`。

### 查询

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/rounds` | 作品列表。参数：`kind=image|video`，`starred=1|0`，`q=关键词`（匹配提示词、模型或编号，支持 `006` 和 `6`），`order=desc|asc`，`offset`，`limit`（≤1000，0 表示全部） |
| GET | `/api/rounds/<id>` | 原图 PNG 或视频 MP4。支持 `ETag` / `If-None-Match`（304）与 `Range`（206），可缓存一年。加 `?download=1` 会带 `Content-Disposition` 直接下载 |
| GET | `/api/rounds/<id>/thumb` | 480px JPEG 缩略图（`has_thumb=true` 才有，不然 404），同样支持 `ETag` / `304` |
| GET | `/api/rounds/<id>/meta` | 作品对象，外加完整的 `meta` 字段 |
| GET | `/api/image` | 最新一张图片（兼容旧版） |

`GET /api/rounds` 返回：
```json
{"rounds":[], "total":12, "rev":34,
 "stats":{"count":20,"images":18,"videos":2,"starred":3,"bytes":31457280}}
```
`total` 是筛选后的数量，`stats` 是整个作品库的统计。

### 收藏

| 方法 | 路径 | body |
|---|---|---|
| POST（或 PATCH） | `/api/rounds/<id>/star` | `{"starred": true}` |
| POST | `/api/rounds/star` | `{"ids":["001","002"], "starred": false}`，返回 `{"ok":true,"updated":[…],"starred":false}` |

收藏的作品在批量清理时默认会被跳过。

### 删除旧照片 / 作品

默认是**移入回收站**，保留 7 天后自动彻底删除，期间可以恢复。带 `permanent: true` 会跳过回收站直接删掉，**没法恢复**。

| 方法 | 路径 | 说明 |
|---|---|---|
| DELETE | `/api/rounds/<id>` | 删一个。`?permanent=1` 表示永久删除。也可以用 `POST /api/rounds/<id>/delete` |
| POST | `/api/rounds/delete` | 批量删除：`{"ids":["001","002"], "permanent": false}`，一次最多 2000 个 |
| POST | `/api/rounds/cleanup` | 按条件清理旧作品，见下面 |

#### `POST /api/rounds/cleanup`

| 字段 | 说明 |
|---|---|
| `older_than_days` | 删掉 N 天前生成的作品（可以是小数，支持 `0`） |
| `keep_latest` | 只保留最新的 N 个，其余的都删 |
| `max_mb` | 按空间上限（MB）清理：单独使用时，从最旧的未收藏作品开始删直到总占用不超过上限 |
| `kind` | `image` / `video`，不填就是全部 |
| `include_starred` | 默认 `false`，收藏的作品不动 |
| `dry_run` | `true` 只返回会删哪些，不真删 |
| `permanent` | `true` 跳过回收站 |
| `expected_ids` | 执行清理必填：同一组条件预览返回的 `matched` 数组 |

`older_than_days`、`keep_latest`、`max_mb` 至少要填一个。`older_than_days` 和 `keep_latest` 同时填时，要**同时满足**才删：不在最新 N 个里，而且早于 N 天。

`max_mb` 不能与日期或保留数量条件共用。先预览，再用同一组条件和预览的作品编号执行；如果命中的编号变化，服务端返回 HTTP 409，且不会删除任何作品。

### 回收站

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/trash` | `{"items":[作品对象 + deleted_at, purge_at], "count", "bytes", "retention_days", "now"}` |
| GET | `/api/trash/<id>` | 预览回收站里的原文件 |
| GET | `/api/trash/<id>/thumb` | 回收站里的缩略图 |
| POST | `/api/trash/restore` | `{"ids":[…]}` → `{"restored":[…],"missing":[…]}`，原编号恢复 |
| POST | `/api/trash/purge` | `{"ids":[…]}` 或 `{"all":true}` → `{"purged":[…],"bytes":N}`，彻底删除 |

服务启动时，以及之后每小时，会自动清掉回收站里超过 7 天的东西。

---

## 6. 参考图 / 首帧 / 尾帧

一共两个槽位：`first`（改图参考图 / 视频首帧 / ref2va 参考图）和 `last`（fl2va 尾帧）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/reference?slot=first|last` | 当前槽位里的图片，没设置返回 404 |
| POST | `/api/reference?slot=first|last` | **请求体直接放图片二进制**（PNG / JPEG / WebP，≤ 12MB） |
| DELETE | `/api/reference?slot=first|last` | 清空槽位 |
| POST | `/api/rounds/<id>/use` | 把某个图片作品放进槽位：`{"slot":"first"}` |
| POST | `/api/last-frame` | 兼容旧版，等于 `POST /api/reference?slot=last` |
| POST | `/api/use-latest-image` | 兼容旧版，把最新图片放进 `first` |

---

## 7. Colab 账号和 Hugging Face

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/colab/status` | 强制同步刷新一次 Colab 状态（平时 `/api/status` 是后台异步刷新） |
| POST | `/api/colab/auth/start` | 返回 `{"auth_url":…}`，在浏览器里打开授权 |
| POST | `/api/colab/auth/complete` | `{"code":"4/0A…"}`，成功后返回 Colab 状态并自动唤醒待跑队列 |
| POST | `/api/colab/auth/logout` | 删掉服务器上保存的 Colab 凭据 |
| POST | `/api/colab/hf-token` | `{"token":"hf_…"}` 保存，空字符串表示清除。格式不对返回 400 |
| POST | `/api/hf/list-loras` | `{"repo_id":"owner/repo"}` → `{"files":["a.safetensors",…]}` |
