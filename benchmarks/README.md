# Evaluation data

`python -m app.benchmark --approve` 从 backend 目录运行，使用内置 calculator 快照：
一个自有、刻意植入缺陷的任务，六个路径/代码标记标注的检索查询。

比较 BM25、Qdrant 向量、RRF 混合检索，并实际运行 A/B/C/D 工作流。
默认 demo 是固定补丁，不用于证明多 Agent 比单 Agent 更好。哈希向量不是语义模型。
无 Docker 实际测试时 task_success / patch_test_pass 为 null，不能换成通过率。

输出保存于 results（不提交本地任务与运行数据）；可选择将审查过的汇总复制到 docs。
真实模型实验须配置密钥并选择 `--provider openai`，会产生 API 费用，不能在 CI 自动运行。
`--approve` 仅针对本脚本内置样例，不表示人工介入。对外宣称效果之前，应扩充独立任务、
隐藏验收测试、多次重复运行，固定模型和 Embedding 版本、预算、仓库 commit，并报告置信区间。
