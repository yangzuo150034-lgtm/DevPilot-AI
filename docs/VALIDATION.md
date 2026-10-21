# 验证记录

## 本地验收（2026-10-21，Windows）

- Python 3.12.4 / Node 22.22.0 / npm 10.9.4。
- 后端：46 passed、2 skipped。覆盖快照导入、精确引用、三种检索、审批摘要、拒绝导出、重启恢复、故障恢复、权限与策略、LangChain/Deep Agents 脚本模型契约、MCP stdio 初始化与工具枚举。
- 跳过实际 Docker 和 PostgreSQL/Redis/Qdrant 服务集成：本机未安装 Docker。Qdrant 内存模式已实际测试。
- `pip check`：无依赖冲突。
- 前端 TypeScript 与 Vite 生产构建通过；Playwright 3 项通过，包含批准后 ZIP 下载、拒绝后不可导出、390px 手机布局；已检查截图。
- GitHub REST 真实只读导入成功：octocat/Hello-World，commit `7fd1a60b01f91b314f59955a4e4d4e80d8edf11d`，读取 README，无执行。
- 离线 smoke 评测成功生成真实原始结果，副本见 smoke-results.json。六个查询上的分数只是小样例结果，不是泛化效果。

## 真实服务状态

| 检查 | 状态与证据 |
| --- | --- |
| 真实付费模型调用 | 未运行：没有配置用户模型密钥 |
| Deep Agents API 组合 | 本地脚本模型实际调用适配通过；不是模型质量评测 |
| MCP 协议 | 本地真实 stdio 客户端初始化和工具列表通过 |
| Docker Sandbox 实际执行 | 本机未运行；CI integration 配置独立实测 |
| PostgreSQL Checkpoint / Redis RQ / 远程 Qdrant | 本机未运行；CI integration 配置独立实测 |
| Docker 镜像 / Compose HTTP 闭环 | CI 配置构建与实际 smoke 检查，以对应 commit 日志为准 |
| Windows/Linux 单元与浏览器 CI | 上传后以 GitHub Actions 的实际状态为准 |

## CI 判定规则

`.github/workflows/ci.yml` 包含 backend（Windows/Linux）、frontend build、browser、integration。
integration 在 GitHub Linux runner 启动 PostgreSQL、Redis、Qdrant，执行原版失败/补丁通过的真实 Docker 测试，构建 Compose 并运行经 Nginx/Redis Worker 的 HTTP smoke。
仅配置存在不等于通过；仓库 Actions 中对应 commit 的检查结果才是证据。后续失败应保留日志并修复，不删掉失败测试来换绿色。

## 已知限制

- 固定演示 provider 只支持内置 calculator，不会解决任意 GitHub 任务。
- 仓库导入受限，可能缺少文件或依赖，UI 展示 partial；只导入文本，不安装依赖。
- 测试执行仅支持 stdlib unittest，没有隐蔽验收集；不能凭仓库自带测试证明任意仓库修复正确。
- 单用户共享工作台，无多租户权限模型；本地线程模式只应运行一个 API 实例。
- 线程中断或 Worker 崩溃后的 running 任务不会立即自动重放。可在最后事件超过 20 分钟后调用 retry；queued/failed 可手动重新投递，仍受数据库认领和 checkpoint 保护。
- API 成本、恢复率、人工介入率在缺少定义和原始观测时保留 null；不提供虚构对比。
- 当前没有真实模型、Docker Desktop 或云服务器的本机最终验收，也未自动发布公共服务。
