# 运行与部署

## Windows 本地开发

见根目录 README 的完整命令。默认不需要 Docker、数据库服务或 API Key。
FastAPI 在 8000，Vite 在 5173，绑定 127.0.0.1。默认 SQLite 数据在根目录 `.data`。

需要真实模型时，在根目录 `.env` 配置 `DEVPILOT_OPENAI_API_KEY`、`DEVPILOT_MODEL`；兼容服务可设置 `DEVPILOT_OPENAI_BASE_URL`。模型必须支持 Tool Calling / 结构化输出；模型可用性由你自己的服务账号决定。重启后端后，页面“真实模型”选项可用。密钥只由后端读取，不要发在聊天里或填进前端令牌框。

切换语义向量时配置 `DEVPILOT_EMBEDDING_PROVIDER=openai` 及 Embedding 模型。会产生 Embedding 请求与费用；默认 hash 不产生模型费用。

## Docker Compose（服务部署）

先安装并启动 Docker Desktop 的 Linux containers 后端，或使用 Linux Docker Engine + Compose v2。本次开发机器未安装 Docker；不要将 YAML 配置存在视为部署已成功。

以下命令都在项目根目录。复制配置示例，预期生成不被 Git 跟踪的 `.env`：

```powershell
Copy-Item .env.example .env
```

用编辑器打开 `.env`，设置独立的 `DEVPILOT_POSTGRES_PASSWORD` 和 `DEVPILOT_API_TOKEN`。建议使用随机十六进制值，避免数据库 URL 中的保留字符。下面命令在根目录运行，每次输出一个随机值；用于粘贴到本机 `.env`，不要提交：

```powershell
python -c "import secrets; print(secrets.token_hex(24))"
```

检查 Compose 配置结构，预期无错误；`--quiet` 不输出含密码的展开配置：

```powershell
docker compose config --quiet
```

构建并启动 PostgreSQL、Redis、Qdrant、FastAPI、RQ Worker 和 Nginx/React，预期各容器运行：

```powershell
docker compose up -d --build
```

访问 `http://127.0.0.1:8080`，点击“访问令牌”，输入 `.env` 中的工作台令牌。默认没有把 PostgreSQL/Redis/Qdrant/API 端口公开给宿主网络。网关仅绑定本机；正式外部展示需在可信环境增加 HTTPS 和访问控制。

查看状态，预期服务未退出：

```powershell
docker compose ps
```

查看后端和 Worker 日志，排查问题后按 Ctrl+C 退出日志查看（不停止服务）：

```powershell
docker compose logs -f backend worker
```

停止服务但保留数据卷：

```powershell
docker compose down
```

当前数据库初始化使用 SQLAlchemy `create_all`，适用于新部署；后续表结构变更须添加迁移，不能把它当作已有数据库自动升级工具。备份需覆盖 PostgreSQL 与代码/执行数据；不要直接删除数据卷来解决问题。

## 启用真实隔离测试

当前执行器仅支持自带 `tests/` 的 Python 标准库 unittest 仓库，不自动 pip install 不可信依赖，不支持任意 npm/pytest 脚本。已设置禁网、只读根/源码、非 root、CPU/内存/PID/文件描述符限制、墙钟超时和 16 KB 日志上限。镜像必须提前拉取，运行时不会自动拉取。

在已配置 Docker Desktop 的本地开发方式下，在根目录运行以下命令拉取官方 Python 镜像，预期下载成功：

```powershell
docker pull python:3.12-slim
```

随后在 `.env` 设置 `DEVPILOT_SANDBOX_ENABLED=true` 并重启后端。演示原始版本应测试失败，候选补丁应通过；以报告中的 baseline 和 candidate 实际输出为准。

容器化 RQ Worker 要控制外部 Docker daemon，需要额外权限。因此默认 Compose 没有挂 Docker socket。只在专用 Linux Docker 主机/虚拟机上使用 `compose.sandbox.yaml`：在 `.env` 设绝对主机目录 `DEVPILOT_SANDBOX_HOST_DIR=/opt/devpilot-sandbox`，提前创建该目录，再拉取上面的 Python 镜像。预期该目录只存临时文本源码。

在该 Linux 主机的项目根目录检查并启动覆盖配置：

```bash
docker compose -f compose.yaml -f compose.sandbox.yaml config --quiet
docker compose -f compose.yaml -f compose.sandbox.yaml up -d --build
```

第一条只检查，第二条启动。Worker 接收 Docker socket，API 服务不接收；容器内 `/sandbox` 与 Docker 主机 staging 路径显式对应，避免错误挂载。
Docker daemon 控制权限近似主机管理权限，容器共享内核，**这不是面向敌对多租户的安全边界**。使用专用机器、可信管理员和受限访问，不要将此 Worker 直接放在存有重要资料的公共服务器上。下一步可替换为远程微虚拟机执行服务。[Docker 官方安全说明](https://docs.docker.com/engine/security/)

## MCP 与观测

后端运行后，在 backend 目录执行以下命令，预期启动 stdio MCP 服务（等待客户端输入，不是网页）：

```powershell
..\.venv\Scripts\python.exe -m app.mcp_server
```

客户端以此命令和 `cwd=backend` 配置 stdio。只暴露 list_repositories、search_code、get_task_report；访问令牌通过服务端环境传递，不写在工具参数。SDK 使用 mcp 2.x MCPServer API。

LangSmith 为可选。默认不上传追踪；自行配置 `LANGSMITH_TRACING=true`、`LANGSMITH_API_KEY`、`LANGSMITH_PROJECT` 后才启用。追踪可能包含源代码与提示，先确认数据允许外发。
