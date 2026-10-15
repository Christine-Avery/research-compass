# Research Compass 演示讲稿

## 三分钟版本

### 0:00–0:25｜用户问题

“科研探索初期，用户往往只有一个模糊兴趣，连该搜什么关键词都不确定。Research Compass 将搜索从 query/results 改为意图、路径、真实文献和下一步行动。”

### 0:25–1:00｜Page 1：AI Intent Studio

打开 [在线演示](https://research-compass-ai.streamlit.app/?prototype_snapshot=golden&opportunities=v2)。说明公网目前默认规则 V1，实时 Qwen 暂未开放。载入 Golden Case 历史快照，展示 Control Theory、Neural Networks → Gaussian Processes 的研究关系和可编辑意图。强调这是已保存的演示数据，没有现场调用模型。

### 1:00–1:45｜Page 2：Research Path Explorer

展示三条不同探索路径及英文检索式。选路径 1，说明用户选择后读取该路径已保存的真实 OpenAlex 结果（演示快照不新发检索），展示论文 ID、摘要、来源链接和准入状态。提及另外两条路径：2 → Card C（NN 结构与 GP 表达），3 → Card B（在线学习与 GP 更新）。

### 1:45–2:30｜Page 3：Evidence & Next Steps

只展示路径 1 对应的 Card A“稳定性与安全验证”。指出背景事实链接到摘要和 OpenAlex ID，跨路径补充文献单独标注，迁移关系是待验证假设而非证明。修改英文 Next Search 并说明可以继续真实检索。

### 2:30–3:00｜评测与诚实边界

展示单一中文 Golden Case 的规则 V0/V1 指标：branch-macro P@5 为 0.05/0.80 (V0: 1/20 across 4 branches; V1: 12/15 across 3 branches)，nDCG@5 为 0.1077/0.8210。两版分支集合不同，35 条是论文结果记录，不是 35 个查询。该结果不能证明泛化或 Qwen 提升。公开 Qwen 保持关闭，Actionable Research Plan Completion 尚未通过用户研究测量。

## 一分钟版本

“Research Compass 面向科研新手，解决有兴趣但不知道怎么搜索的问题。它让用户确认结构化研究意图、选择探索路径，再检索 OpenAlex 真实论文，并将摘要证据、证据准入和待验证的研究问题分开。线上 MVP 采用 Streamlit、PyAlex/OpenAlex 和规则规划，另有人工策划的 Golden Case v2 演示。单案例规则评测里 V1 指标高于 V0，但两者分支集合不同，不能据此声称泛化或 LLM 提升。公网 Qwen 尚未开放，下一步是修复并验证未知模型请求的并发槽恢复，再做更多独立查询和用户任务评测。”
