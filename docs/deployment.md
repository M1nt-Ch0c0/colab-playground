# 部署与运维

ColabReel 支持单机自托管。优先从 [Docker Compose 快速开始](../README.md#快速开始) 安装。工作台、作品库和队列数据由部署者管理，生成需要访问 Google Colab；部署成功不代表账号有可用的 GPU 或额度。

## Docker 与数据目录

`docker-compose.yml` 缺省只把服务发布到宿主机的 `127.0.0.1:8787`，容器里的 `/data` 映射到项目根目录下的 `data/`。容器进程以 UID 1000 运行；如果新建的数据目录或配置文件不可读写，请在宿主机将归属调整为运行用户，不要放宽凭据文件的权限。

- 对外访问时使用 HTTPS 反向代理和适当的访问限制，不要直接开放后端端口。若代理转发客户端地址，只信任自己的入口代理。Colab 工作进程在远端下载模型权重；宿主机保存运行配置、队列、素材和成品。
- 在设置里授权 Google Colab、添加可选的改写模型和代理线路。代理线路可单独命名、测试、切换和删除，编辑时地址留空会保留原凭据。
- 停服后备份整个数据目录，包括作品、队列、工作流与配置；备份包含敏感凭据，应加密保存。不要在同一数据卷上并行运行两个实例。

## 不使用 Docker

安装 Python 3.13、Node.js 22.12+ 和 FFmpeg（含 `ffprobe`，视频相关功能需要）。在项目目录运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build
cp -n secret.env.example secret.env
chmod 600 secret.env
# 将 secret.env 中的 password 和 token 改为独立的强随机值
python3 app.py
```

Windows PowerShell 的虚拟环境激活命令是 `.venv\Scripts\Activate.ps1`。启动后从本机浏览器访问 [http://127.0.0.1:8787](http://127.0.0.1:8787)。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `QP_ROOT` | 程序所在目录（Docker 内为 `/data`） | 数据与凭据存放根目录 |
| `QP_SECRET` | `$QP_ROOT/secret.env` | 配置文件路径 |
| `QP_HOST` | `127.0.0.1`（Docker 内为 `0.0.0.0`） | 监听地址 |
| `QP_PORT` | `8787` | 监听端口 |
| `QP_IDLE_SECONDS` | `600` | 默认空闲自动释放秒数（页面可调 5–60 分钟，或设为永不超期） |
| `QP_TRASH_DAYS` | `7` | 回收站自动清理保留天数 |

## GitHub 自动发布（维护者）

推送 `v*` 标签或手动运行 `Build, Push to GCP Artifact Registry & Deploy` 会执行测试。镜像发布目标由 GitHub 仓库的 **Settings → Secrets and variables → Actions** 提供。

| 类型 | 名称 | 用途 |
|---|---|---|
| Variable | `IMAGE_REPO` | 完整 Artifact Registry 镜像路径，格式为 `LOCATION-docker.pkg.dev/PROJECT/REPOSITORY/IMAGE`，省略标签 |
| Secret | `GCP_AR_SA_KEY` | 有镜像推送权限的服务账号凭据 |
| Variable | `DOKPLOY_URL` | 可选部署的 Dokploy HTTPS 根地址 |
| Variable | `APP_HEALTH_URL` | 目标应用完整的 `/healthz` 地址，部署前检查空闲，部署后确认实际运行的构建 |
| Secrets | `DOKPLOY_API_KEY`、`DOKPLOY_APP_ID` | 目标 Dokploy 应用的部署凭据和 ID |
| Secrets | `CF_ACCESS_CLIENT_ID`、`CF_ACCESS_CLIENT_SECRET` | 可选，仅用于受 Cloudflare Access 保护的 Dokploy 入口 |

配置前两项即会自动推送带版本标签和 `:latest` 的镜像。补齐部署配置后，工作流会在镜像推送成功、目标服务空闲时调用 Dokploy，再等待健康接口返回本次运行的 `build_id`。五分钟后仍读到旧构建或无法访问时，发布检查会失败。手动触发的 `force_deploy` 会跳过空闲等待，可能打断正在运行的任务。强制部署时若省略 `APP_HEALTH_URL`，工作流只能确认 Dokploy 已接受请求。

在 Dokploy 的 Swarm 设置中，将副本数设为 1，更新和回滚的 `Order` 都设为 `stop-first`。进程会独占数据卷上的 SQLite 锁，需要先停止旧容器再启动新容器。切换期间服务会短暂不可用。

## 安全与访问

- **凭据保护**：`secret.env`、`colab_token.json`、`hf_token.txt` 和 `private/` 下的模型与代理配置均只存服务端且权限为 `0600`，日志自动脱敏 Hugging Face Token 与代理账密，网页端绝不回显代理密码。
- **反暴力登录**：同一 IP 10 分钟内输错密码 8 次自动限流（HTTP 429）。
- **接口文档**：所有接口均支持浏览器 Cookie 或 `Authorization: Bearer <token>` 自动化调用，详见 [HTTP API](API.md)。
