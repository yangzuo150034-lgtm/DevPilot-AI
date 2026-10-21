# DevPilot AI 项目计划

## 定位与业务

构建可以部署、复现测试并在面试中解释的 AI 软件工程协作平台。输入 GitHub 仓库地址与任务，输出有代码位置证据、Git Diff、隔离测试结果和审批记录的解决方案。PR 创建后续单独实现。

## 目标架构（尚未全部实现）

```text
React / TypeScript / Vite
  → FastAPI / Pydantic
  → LangGraph Supervisor / Checkpoint / Human Approval
      → Planner / Research / Coding / Review
      → LangChain Models / Tools / RAG / Middleware
      → Deep Agents 能力适配（先验证组合方式）
      → 自研 Harness：权限、预算、超时、执行、安全与观测
  → GitHub API / MCP / Qdrant / PostgreSQL / Redis + RQ
  → Docker Sandbox（执行不可信代码）
```

LangGraph 管理唯一顶层业务生命周期。Deep Agents 是否作为某一工作节点或采用其兼容能力，须通过小型集成实验确定，避免重复任务调度、审批与恢复。RQ 负责后台任务投递，不管理 Agent 推理循环。Checkpoint 保存工作流状态，PostgreSQL 保存业务实体和执行记录；长期知识与向量索引另行分层。

## 初始目录及扩展边界

```text
AGENTS.md                    长期协作要求
README.md                    当前能力与运行指南
docs/PROJECT_PLAN.md         架构、路线、验收
backend/
  app/main.py                应用工厂与路由装配
  app/api/health.py           健康检查路由及响应契约
  tests/test_health.py        API 契约测试
  pyproject.toml              元数据、直接依赖、Ruff/Pytest 配置
  requirements.lock          当前解析出的 Python 精确依赖
frontend/
  src/App.tsx                连接状态界面
  src/api.ts                 API 请求与响应验证
  src/styles.css             基础响应式样式
  package.json               命令与直接依赖
  package-lock.json          npm 精确依赖
.github/workflows/ci.yml     后端测试、静态检查、前端构建
```

仅按需创建 agents、rag、harness、repositories、workers、benchmarks、infra 等模块，不提前堆空目录。

## 阶段一 MVP 实施清单与验收

本阶段是基础工程 MVP，不是完整 Agent 产品。

| 实施项 | 可验证验收标准 |
| --- | --- |
| 检查环境 | 记录工具路径、版本、缺失项，不假设已配置 |
| Python 隔离 | 使用项目 .venv，不污染 Anaconda 全局包 |
| FastAPI | GET /api/v1/health 返回 200 与约定 JSON；/docs 可访问 |
| React + TypeScript | 页面清楚标识当前阶段；请求真实健康接口；加载、失败、重试可见 |
| 开发联调 | Vite 将 /api 代理至本机 8000 端口，不引入宽泛 CORS |
| 后端检查 | Pytest 验证健康接口、OpenAPI、未知路径；Ruff 检查通过 |
| 前端检查 | TypeScript 检查与 Vite 生产构建通过 |
| 集成验证 | 启动本地后端与 Vite，经前端代理实际获取健康 JSON |
| 可复现 | README 提供 Windows 命令、目录、预期结果；两端依赖锁定 |
| CI 与安全 | CI 执行相同核心检查；忽略密钥、环境、缓存、构建产物 |

阶段一不实现：模型 API、GitHub 导入、任务队列、数据库、RAG、多 Agent、沙箱、补丁执行或 PR。前端构建产物需由后续部署反向代理转发 /api，Vite 开发代理不等于生产部署。

## 关键选择与取舍

- 单仓库、前后端分目录：便于一个人联调与统一 CI；暂不需要多仓库发布流程。
- Python 内置 venv + pip：现有环境可用，不要求先安装 uv；锁定当前 Python 3.12 依赖。venv 不能隔离恶意代码。
- React + Vite SPA：适合独立 API 的交互工作台；相比 Next.js 少一层服务端运行时，但未来路由与数据缓存需要按需选型。
- 初期普通 CSS：减少安装和学习范围；进入工作台阶段再引入 Tailwind，不影响目标技术栈。
- 健康检查只表示本服务存活；未来数据库、队列等就绪状态使用独立 readiness 契约，不能假称依赖健康。
- 本地开发绑定 127.0.0.1；不默认暴露局域网，不配置通配跨域。
- Docker 未安装不阻塞可信自有基础代码开发，但必须阻塞任何不可信仓库代码执行。

## 十周路线（按验收推进，可调整日历）

| 周 | 交付内容 | 阶段出口 |
| --- | --- | --- |
| 1 | Windows 环境、FastAPI、React、Git 基础、文档与 CI | 基础联调及检查通过 |
| 2 | GitHub API、受限仓库导入、文件读取、结构与依赖分析 | 合法仓库可导入，有大小/路径/凭据边界，不执行仓库代码 |
| 3 | LangChain Models、Tools、Middleware、单 Agent | 有预算与可追踪工具调用的单任务闭环 |
| 4 | Tree-sitter、Embedding、Qdrant、代码 RAG | 引用路径/行号可验证，建立关键词检索基线 |
| 5 | LangGraph StateGraph、Supervisor、角色协作 | 明确状态契约、权限、路由与终止条件 |
| 6 | Deep Agents 集成实验、Planning、Subagents、Skills | 一个调度主线，技能有输入输出与测试 |
| 7 | Harness、安全执行、上下文预算、补丁审批 | Docker 隔离测试，审批绑定具体补丁与版本，拒绝可验证 |
| 8 | PostgreSQL、Checkpoint、Redis/RQ、React 工作台 | 重启可恢复任务，执行轨迹可查看 |
| 9 | LangSmith、Benchmark、消融实验与优化 | 原始结果可复现，无虚构指标 |
| 10 | Docker Compose、CI、技术文档、演示 | 按 README 可部署并完成演示任务 |

## RAG 与实验设计

RAG：仓库导入 → 路径/语言过滤 → Tree-sitter 结构分块 → Embedding 与关键词索引 → Hybrid Search → Reranking → 文件路径、行号、commit 引用；索引以仓库版本标识并支持更新。
比较关键词、向量、混合检索；标注真实相关代码集合，计算 Recall@5 和 MRR。

Agent 消融：A 基础 LangChain Single-Agent；B Single-Agent + RAG；C LangGraph Multi-Agent + RAG；D 再增加 Harness。统一仓库版本、任务、模型配置、工具预算和环境，并记录重复次数、失败与超时。成功率与补丁通过率基于预先定义的验收测试；成本基于真实 Token 与当时价格；人工介入与恢复率明确定义分母。

## 初始环境记录（2026-10-21）

- 工作区初始为空，非 Git 仓库。
- Python 3.12.4 位于 Anaconda；另有 Python 3.9，不使用它。
- Git 2.45.2.windows.1；Node.js 22.22.0；npm.cmd 10.9.4。
- npm.ps1 被执行策略阻止，使用 npm.cmd，不修改机器策略。
- Docker / Compose / uv 未在 PATH 找到；Docker 默认安装位置不存在。不能据此排除其他自定义安装位置。
- Docker 安装与实际启动验证留待沙箱阶段前完成；uv 为可选工具。

## 官方依据与后续参考

本阶段已核对：
- https://fastapi.tiangolo.com/tutorial/first-steps/
- https://vite.dev/guide/
- https://react.dev/learn/build-a-react-app-from-scratch
- https://docs.python.org/3.12/library/venv.html

后续接入前再阅读对应官方版本文档：LangChain、LangGraph、Deep Agents、Qdrant、MCP Python SDK、Docker。架构参考仓库（本阶段尚未做源码分析）：langchain-ai/langgraph、langchain-ai/langchain、langchain-ai/deepagents、crewAIInc/crewAI、microsoft/autogen、browser-use/browser-use、langgenius/dify。

## 执行状态

用户已调整为“先完成项目，再逐步学习”，并授权上传私有 GitHub 仓库。已开发 0.2.0 核心闭环；以下矩阵优先于原始十周日历。测试记录见 VALIDATION.md，学习顺序见 LEARNING_GUIDE.md。

| 原路线能力 | 当前实现 | 尚需深化或验收 |
| --- | --- | --- |
| 基础工程 | FastAPI / React / Tailwind / 测试 / CI | 以远程 CI 日志确认跨平台 |
| 仓库导入 | GitHub commit/tree/blob、过滤与静态快照 | 大仓库、更多语言、细粒度索引更新 |
| LangChain 单 Agent | A/B 结构化编码调用 | 用户配置真实模型后的质量验证 |
| RAG | Tree-sitter、BM25、Qdrant、可选语义向量、RRF | 学习型 reranker、增量与大规模成本 |
| 多 Agent | C/D 规划/确定性检索/编码/审查，角色契约明确 | 更复杂动态路由和修复循环 |
| Deep Agents | D Coding 节点、StateBackend、只读工具 | 动态 Skills 与通用子代理扩展 |
| Harness | 调用/上下文预算、补丁摘要、审批、Docker 执行器 | 通用语言测试、微虚拟机隔离 |
| 持久化与 UI | SQLite 默认、PostgreSQL/RQ 适配、检查点、工作台 | 表结构迁移、多用户、SSE |
| 观测与评测 | 事件、Token callback、可选 LangSmith、真实 smoke runner | 真实模型 A-D 重复实验及统计结论 |
| 部署与展示 | Dockerfile、Compose、CI、学习/部署/架构文档 | 真实密钥与部署环境最终验收、云托管 |

“代码已实现”“脚本替身验证”“真实服务集成验证”是不同状态，不把尚未验收的服务称为已稳定生产。PR 创建仍作为后续独立授权功能。
