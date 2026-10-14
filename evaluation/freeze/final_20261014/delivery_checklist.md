# Research Compass · 最终交付清单（冻结候选）

## 可演示成果

- Streamlit 网页：模糊兴趣输入、最多两道可跳过的澄清题、可编辑的结构化意图、可选择和修改的探索分支。
- OpenAlex/PyAlex 真实论文检索：标题、年份、摘要、来源链接、原始排名；明确标记网络失败时的 Demo 数据。
- V0 Day 1 关键词 Baseline 与 V1 规则方案并存；论文标为 Retrieved / Relevant / Evidence Eligible，研究版图仅使用准入摘要，事实摘录附来源，候选问题标记为待验证；支持 JSON Trace 导出。
- Evaluation 页面：35 条论文的人工相关性和证据准入标注、定向复核及逐次修改日志。当前复核版 35/35 条均有相关性和准入标签；NLP 论文的**最终裁定仍待定**。
- Qwen 规划接口存在，但历史测试 2/2 请求失败；**没有证明 Qwen 比规则方案有效**，交付演示应选规则 V1。此冻结不调用 Qwen。

## 已验证的范围

- 一条 Golden Case 的 Live OpenAlex 快照：V0 四分支 20 条（13 个唯一论文 ID），V1 三分支 15 条（15 个唯一论文 ID）。这不是多案例总体评测。
- 按现有人工相关性标签，V0 Precision@5 为 1/20、nDCG@5 为 0.1077；V1 为 12/15、0.8111。相关性阈值 ≥1；nDCG 使用 0/1/3 增益；版本值为分支宏平均。**V1 的 NLP 标签待裁定，排名指标也应标为暂定。**
- V1 系统准入 8 条，人工相关性 0 的准入为 0/8。两篇 GP 控制论文相关性仍为 2，但用户确认其摘要不必进入当前 Evidence Generation；它们在最终裁定版中不计误拒绝。
- V0 无 Evidence Gate，不能报告其 Gate Precision/Recall。V1 Gate 的最终 Recall 在 NLP 标签裁定前为 N/A；不要继续引用上一轮 8/11 的有争议结论。具体已裁定样本计数见 `gate_metrics.json`。

## 尚未实现或验证

- 无全文 PDF 核验、系统综述覆盖度保证、已证实 Research Gap 或可靠的引文支持率；页面证据范围仅为已检索摘要。
- 无多案例人工质量结论、统计显著性、线上部署稳定性证明，也无 Qwen 成功调用带来的质量/成本收益结论。
- `comparison_transfer` 检索分支仍有偏离控制理论与 NN→GP 迁移目标的结果。NLP 论文的人工标签与复核理由冲突，需单独裁定后再定稿 Gate Recall。

## 用于 PRD / 作品集 / 简历的安全表述

> 构建了面向模糊科研兴趣的探索式搜索 MVP：以可编辑意图和研究分支驱动 OpenAlex 检索，展示可追溯的摘要证据，并设计 V0/V1 配对人工评测和逐条修正机制。单一 Golden Case 的 V1 检索 Precision@5 为 12/15；跨案例效果、证据生成质量和 LLM 增益仍待验证。

冻结包和逐文件 SHA-256 见 `freeze_manifest.json`。本次仅整理与裁定，不修改检索、规划或 Evidence Gate 算法，不包含 `.env`、真实 Secrets 或 API Key。
