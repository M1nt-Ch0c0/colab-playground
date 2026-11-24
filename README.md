# Colab Studio (`colab-playground`)

轻量级、单机自托管的 **Google Colab 云端 GPU 生图 / 改图 / 生视频工作台**。

无前端构建步骤、无数据库依赖，整个服务端仅由 **6 个 Python 文件**构成；直接以 SDK 方式调用官方 `google-colab-cli` 协议，按需租用 Google Colab GPU（G4 / H100 / A100 / L4 / T4），模型常驻云端显存复用，空闲超时自动释放停止计费。

---

## 核心特性

- **双生图引擎切换**
  - **Diffusers（整机）**：内置 `Qwen/Qwen-Image-2.1`（BF16 / Q5 GGUF）、`black-forest-labs/FLUX.2-dev`，也支持直接填写任意 Hugging Face Diffusers 仓库（`owner/repo`）并保存「最近使用」。
  - **ComfyUI（三件套单文件）**：在 Colab 端自动拉起常驻 `ComfyUI` 本地服务（大显存自动 `--highvram`），按模板（`Qwen-Image 2.1` / `FLUX` / `通用三件套`）分别粘贴扩散模型（`BF16 / NVFP4 / FP8 / GGUF`）、文本编码器与 VAE 链接，支持保存/一键切换自定义组合方案与多槽位 LoRA。
- **文生视频 + 同步音频**：内置 `MiniMaxAI/MiniMax-H3`（33B），支持 `t2va`（文生视频）、`fl2va`（首帧/首尾帧）、`ref2va`（参考图），输出带音轨 MP4。
- **参考图改图 & 连续编辑**：支持上传/拖拽/粘贴参考图，以及「接着改」（自动取最新作品为参考图）。
- **多卡轮询 + 跨代理热切换**
  - 实时展示账号可用 GPU、运行复用状态与 30 分钟内分配实测状态；
  - 支持勾选指定多张 GPU 按顺序轮询、设置轮询轮数（1–10 轮）、开启跨全部已配代理（US / SG / 自定义）轮询，并支持 `High-RAM → Standard` 503 自动降级；
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
 OpenAI 兼容接口（可选）        本地磁盘 out/                   出站代理（US/SG/自定义）
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

| 路径 | 说明 |
|---|---|
| `app.py` | 标准库 `ThreadingHTTPServer`、登录/Token 鉴权、全部 `/api/*` 路由与优雅停机 |
| `ui.py` | 单文件内嵌 HTML/CSS/JS 前端（无构建步骤、无外部 CDN） |
| `jobs.py` | 持久化任务队列、参数校验、HF 链接解析、ComfyUI 组合方案、代理热切换、空闲自动释放与 AI 改写 |
| `store.py` | 作品库、图片尺寸探测、存储统计、收藏、批量清理、7 天回收站、`ETag`/`Range` 媒体流 |
| `colab_backend.py` | 基于 `google-colab-cli` 内部类的 OAuth2 授权、异步 CU 查询、多卡/多代理轮询、Kernel 中断与日志脱敏 |
| `colab_worker.py` | 上传到 Colab GPU 执行的远端 Worker（Diffusers + ComfyUI 双引擎与显存互斥管理） |
| `docs/API.md` | 完整 HTTP REST API 文档 |
| `Dockerfile` / `docker-compose.yml` | 容器化部署配置 |
| `deploy/colab-playground.service` | Linux systemd 服务单元示例 |
| `tests/` | 后端与 ComfyUI 单元测试 |

---

## 快速开始

### 方式一：Docker Compose（推荐）

```bash
mkdir -p data
cp secret.env.example data/secret.env
chmod 600 data/secret.env
# 编辑 data/secret.env，修改 password 和 token（及可选的代理 / AI 改写配置）
vim data/secret.env

docker compose up -d --build
```

打开浏览器访问 `http://127.0.0.1:8787`，登录后在右上角「设置」中完成 Google Colab OAuth 授权即可使用。

### 方式二：Python 虚拟环境直接运行

需要 Python 3.11+（推荐 3.13）：

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

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
| `QP_IDLE_SECONDS` | `600` | 默认空闲自动释放秒数（可在页面调 5–60 分钟） |
| `QP_TRASH_DAYS` | `7` | 回收站自动清理保留天数 |

---

## 安全与运维提示

- **凭据保护**：`secret.env`、`colab_token.json`、`hf_token.txt`、`proxy_custom.txt` 均只存服务端且权限为 `0600`，日志自动脱敏 Hugging Face Token 与代理账密，网页端绝不回显代理密码。
- **反暴力登录**：同一 IP 10 分钟内输错密码 8 次自动限流（HTTP 429）。
- **接口文档**：所有接口均支持浏览器 Cookie 或 `Authorization: Bearer <token>` 自动化调用，详见 [docs/API.md](docs/API.md)。

## 许可

[MIT License](LICENSE)
