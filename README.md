# Colab Studio (`colab-playground`)

轻量级、单机自托管的 **Google Colab 云端 GPU 生图 / 改图 / 生视频工作台**。

React 工作台由 Python FastAPI 同源托管。服务端通过 `google-colab-cli` 按需申请 GPU，复用常驻模型，并按空闲计时释放实例。设置里可配置 OpenAI 兼容、Anthropic 和 Gemini 改写模型，增强改写可按服务商开启。

---

## 核心特性

- **双生图引擎切换**
  - **Diffusers（整机）**：内置 `Qwen/Qwen-Image-2.1`（BF16 / Q5 GGUF）、`black-forest-labs/FLUX.2-dev`，也支持直接填写任意 Hugging Face Diffusers 仓库（`owner/repo`）并保存「最近使用」。
  - **ComfyUI（三件套单文件）**：在 Colab 端自动拉起常驻 `ComfyUI` 本地服务（大显存自动 `--highvram`），按模板（`Qwen-Image 2.1` / `FLUX` / `通用三件套`）分别粘贴扩散模型（`BF16 / NVFP4 / FP8 / GGUF`）、文本编码器与 VAE 链接，支持保存/一键切换自定义组合方案与多槽位 LoRA。
- **文生视频 + 同步音频**：内置 `MiniMaxAI/MiniMax-H3`（33B），支持 `t2va`（文生视频）、`fl2va`（首帧/首尾帧）、`ref2va`（参考图），输出带音轨 MP4。
- **参考图改图 & 连续编辑**：支持上传/拖拽/粘贴参考图，以及「接着改」（自动取最新作品为参考图）。
- **多卡轮询 + 跨代理热切换**
  - 实时展示账号可用 GPU、运行复用状态与 30 分钟内分配实测状态；
  - 支持勾选指定多张 GPU 按顺序轮询、设置轮询轮数（1–10 轮）、开启跨已保存的代理线路轮询，并支持 `High-RAM → Standard` 503 自动降级；
  - 取消任务时真正向 Colab Jupyter Kernel 发 `interrupt`（必要时自动 2 秒重启 Kernel，保留 GPU 实例与磁盘已下载模型）。
- **任务队列与作品库**：磁盘持久化队列与历史（服务重启自动恢复）、批量出图（1–4 张种子递增）、实时进度条与日志、收藏/搜索/筛选/复用参数、7 天回收站与按天数/数量/空间上限清理。
- **亮色 / 暗色双主题**：默认亮色模式，支持一键切换暗色并本地持久化；桌面端自适应双栏独立滚动布局。
- **AI 提示词改写（可选）**：接入任意 OpenAI 兼容 `/v1/chat/completions` 接口，一句话扩写为高质量生图/生视频提示词。

---

## 架构概览

```text
浏览器 ──▶ 反向代理 / Tunnel ──▶ colab-playground (127.0.0.1:8787)
                                       │
       ┌───────────────────────────────┼───────────────────────────────┐
       ▼                               ▼                               ▼
 改写模型服务商（可选）        本地磁盘 out/                   可配置的出站代理
 AI 提示词改写                 作品库 / 回收站 / 队列           仅走 Colab 控制面与回图
                                                                       │
                                                                       ▼
                                                            Google Colab GPU 实例
                                                            ├── Diffusers（常驻 Kernel）
                                                            ├── ComfyUI（常驻 :8188）
                                                            └── 机房直连 Hugging Face 下权重
```

> 大模型权重全部在 Colab 云端机房直连 Hugging Face 下载，不占用宿主机磁盘，也不消耗代理流量；宿主机只保存代码、队列状态与生成的成品图/视频。

### 目录结构

```text
app.py                       启动入口，也可供 uvicorn app:app 加载
draw_studio/
  application.py             FastAPI 应用、路由装配与静态页面
  runtime.py                 服务初始化、队列恢复和数据卷锁
  api/                       工作台、作品库、工作流和改写模型的 HTTP 接口
  generation/                生成队列、模型目录、参数校验和 H3 写作指南
  workflows/                 模板定义、运行引擎、网页素材和 FFmpeg 拼接
  colab/                     宿主机客户端 client.py、上传到 GPU 的独立 worker.py
  gallery.py                 作品文件、索引、缩略图和回收站
  llm.py                     模型服务商配置与协议适配
  legacy_ui.py               /legacy 页面
web/                         React / TypeScript 工作台
tests/                       领域测试、HTTP 契约与浏览器联调
deploy/                      systemd 示例
```

运行数据由 `QP_ROOT` 指定。默认是仓库根目录，容器内是 `/data`。源码中的 `draw_studio/workflows/` 定义工作流，用户的运行记录保存在 `$QP_ROOT/workflows/runs/`。[后端设计与运行说明](docs/backend-redesign.md) · [HTTP API](docs/API.md)

---

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
mkdir -p data
cp secret.env.example data/secret.env
chmod 600 data/secret.env
# 编辑 data/secret.env，修改 password 和 token
vim data/secret.env

docker compose up -d --build
```

打开浏览器访问 `http://127.0.0.1:8787`，在右上角「设置」中完成 Google Colab OAuth 授权。改写服务商和代理线路也在设置中添加。每条代理可以单独命名、测试、切换和删除，编辑时地址留空会保留已保存的凭据。

### 方式二：Python 虚拟环境直接运行

使用 Python 3.13 和 Node.js 22.12+ 构建。

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build

cp secret.env.example secret.env
chmod 600 secret.env
# 编辑 secret.env 填入 password 与 token

python3 app.py
```

### 常用环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `QP_ROOT` | 程序所在目录（Docker 内为 `/data`） | 数据与凭据存放根目录 |
| `QP_SECRET` | `$QP_ROOT/secret.env` | 配置文件路径 |
| `QP_HOST` | `127.0.0.1`（Docker 内为 `0.0.0.0`） | 监听地址 |
| `QP_PORT` | `8787` | 监听端口 |
| `QP_IDLE_SECONDS` | `600` | 默认空闲自动释放秒数（页面可调 5–60 分钟，或设为永不超期） |
| `QP_TRASH_DAYS` | `7` | 回收站自动清理保留天数 |

---

## GitHub 自动发布

推送 `v*` 标签或手动运行 `Build, Push to GCP Artifact Registry & Deploy` 会执行测试。镜像发布目标由 GitHub 仓库的 **Settings → Secrets and variables → Actions** 提供。

| 类型 | 名称 | 用途 |
|---|---|---|
| Variable | `IMAGE_REPO` | 完整 Artifact Registry 镜像路径，格式为 `LOCATION-docker.pkg.dev/PROJECT/REPOSITORY/IMAGE`，省略标签 |
| Secret | `GCP_AR_SA_KEY` | 有镜像推送权限的服务账号凭据 |
| Variable | `DOKPLOY_URL` | 可选部署的 Dokploy HTTPS 根地址 |
| Variable | `APP_HEALTH_URL` | 目标应用完整的 `/healthz` 地址，部署前用于等待空闲 |
| Secrets | `DOKPLOY_API_KEY`、`DOKPLOY_APP_ID` | 目标 Dokploy 应用的部署凭据和 ID |
| Secrets | `CF_ACCESS_CLIENT_ID`、`CF_ACCESS_CLIENT_SECRET` | 可选，仅用于受 Cloudflare Access 保护的 Dokploy 入口 |

配置前两项即会自动推送带版本标签和 `:latest` 的镜像。补齐部署配置后，工作流会在镜像推送成功、目标服务空闲时调用 Dokploy。手动触发的 `force_deploy` 可跳过空闲等待。

## 安全与运维提示

- **凭据保护**：`secret.env`、`colab_token.json`、`hf_token.txt` 和 `private/` 下的模型与代理配置 均只存服务端且权限为 `0600`，日志自动脱敏 Hugging Face Token 与代理账密，网页端绝不回显代理密码。
- **反暴力登录**：同一 IP 10 分钟内输错密码 8 次自动限流（HTTP 429）。
- **接口文档**：所有接口均支持浏览器 Cookie 或 `Authorization: Bearer <token>` 自动化调用，详见 [docs/API.md](docs/API.md)。

## 许可

[MIT License](LICENSE)
