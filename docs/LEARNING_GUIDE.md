# 从使用到理解：学习这份项目

## 先完成一次演示

启动两端，打开 5173。导入演示仓库，查看 calculator.py 中的减法错误；创建默认任务；阅读执行计划与引用；核对 Diff；先拒绝一次，再新建任务并批准；下载 ZIP，比较原快照与候选源码。
没有 Docker 时看到“已批准 · 未验证”是正确结果，不等于修复已经通过测试。

## 推荐阅读顺序

1. `backend/app/api/health.py`：一个 HTTP 请求如何变成 JSON，Pydantic 响应模型有什么作用。
2. `frontend/src/client.ts`、`App.tsx`：浏览器请求、状态、表单与错误处理；Vite 代理为何让浏览器无需跨域。
3. `schemas.py`、`storage.py`：API 契约与数据库表为什么分开；为什么记录固定 commit。
4. `repositories.py`、`core/security.py`：GitHub tree/blob API、大小限制、路径与秘密文件过滤；为什么不能直接运行外部代码。
5. `rag/chunks.py`、`rag/search.py`：分块、引用、BM25、哈希向量、Embedding、Qdrant、RRF。分别运行三种检索，观察排名差异。
6. `agents/workflow.py`：从 START 顺着边走到 END；找到 interrupt 和 Command(resume)，解释为何关闭服务后仍能审批。
7. `agents/models.py`：结构化输出与实际 LLM 调用；三个模型角色与确定性 Research 的区别；D 配置如何组合 Deep Agents。
8. `harness/patches.py`、`sandbox.py`：模型为什么不能自批补丁，摘要如何防止改包，Docker 参数限制了什么。
9. `tests/`：先读 test_workflow.py，再读 security/recovery/model_contracts；区分脚本模型测试与真实服务测试。
10. `compose.yaml`、`ci.yml`：服务间通信、后台队列、自动检查；学习 CI 日志如何支持 README 的声明。

## 可自己动手的小练习

- 为健康接口增加一个无敏感信息的字段，先改测试，再改后端和前端契约。
- 改变检索查询，记录三种模式结果；不要因为六个样例得分高就下结论。
- 在测试中模拟 Coding 节点超时，确认重试不会重复 Planner。
- 尝试用旧 digest 批准补丁，解释为什么后端返回 400。
- 配置 Docker 后查看“原版失败、候选通过”的真实日志，再扩展一个自有 unittest 任务。

## 面试时如何诚实讲解

可以讲清：你要解决的业务问题、组件边界、固定快照与证据、状态持久化、模型不可信、审批摘要、隔离执行和消融实验方法。
不要声称：所有代码都由自己独立从零手写、哈希向量是语义模型、一个固定样例证明多 Agent 优越、未运行过的真实模型/部署已稳定生产。

建议表述：“我用 AI 辅助搭建工程，随后通过阅读模块、补充测试和独立扩展掌握它。这是单用户作品级平台；我能解释这些取舍，也知道它尚未达到多租户生产安全要求。”

最终竞争力来自你能独立定位一个问题、解释设计并做出受测试保护的修改。先运行，再顺着一次请求读代码，最后独立加一个能力。
