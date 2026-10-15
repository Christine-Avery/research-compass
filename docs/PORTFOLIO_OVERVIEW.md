# Research Compass — Portfolio Overview

**一句话定位：** 帮助科研新手把模糊兴趣转化为可检查的研究路径、真实文献证据和下一步搜索。

**Demo:** [research-compass-ai.streamlit.app](https://research-compass-ai.streamlit.app/) · **GitHub:** [Christine-Avery/research-compass](https://github.com/Christine-Avery/research-compass)

## 用户痛点与需求来源

产品问题来自项目发起者对科研探索初期的观察：新手常有主题兴趣，却不知道学术术语、检索分支和如何形成可验证问题。该问题作为产品假设进入 MVP；尚未进行代表性访谈，也没有宣称用户研究验证。

## 三页体验

1. **AI Intent Studio**：输入兴趣，查看和编辑结构化意图；公开版默认规则 V1，实时 Qwen 暂未开放。历史 Golden Case 载入明确标为快照。
2. **Research Path Explorer**：查看路径目标与英文查询，用户选路后检索 OpenAlex；显示摘要、来源链接、ID、原始排名及筛选说明。
3. **Evidence & Next Steps**：分开呈现摘要支持、证据准入、待验证研究假设、证据缺口和可修改的下一轮查询。

### 页面原型

- [Intent Studio](prototypes/01_AI_Intent_Studio.png)
- [Path Explorer](prototypes/02_Research_Path_Explorer.png)
- [Evidence & Next Steps](prototypes/03_Evidence_Next_Steps.png)

三张 PNG 均为 1440×900 像素的真实浏览器页面视口截图，未把小图扩画布或填充空白。Page 3 展示路径 1 → Card A 的 Golden Case v2 状态；卡片内容在视口下方可滚动查看。线上映射为 path1→A 稳定性与安全、path2→C NN 结构与 GP 表达、path3→B 在线学习与 GP 更新。该页面为人工策划历史案例，不是 Qwen 实时结果。

## 关键产品决策

- 复用 OpenAlex/PyAlex，有限时间聚焦探索流程而非自建论文库。
- 用户确认意图并选择路径后才检索；已查路径使用会话缓存。
- 区分 relevance、Evidence Generation eligibility 和 claim support，避免把无关或不支持的摘要带入研究版图。
- 小检索集合不宣称“无人研究”；迁移建议标为假设，摘要不冒充全文。
- 保留规则降级及 Qwen 默认关闭；预算、并发和未知请求处理未过云端安全门前不开放付费调用。

## 真实评测与一个 Bad Case

冻结评测只有一个中文 Golden Case。V0 20 条检索结果，P@5=0.05、nDCG@5=0.1077；V1 15 条，P@5=0.80、nDCG@5=0.8111。共有 35 条分支级论文判断，V0/V1 分支集合不同；这些结果不证明统计显著、跨主题泛化或 Qwen 提升。核心 Bad Case 中，中文复杂意图被转成弱查询，多个分支语义接近，无关结果污染证据。处理方式是冻结并保留 Trace、人工标注意图与迁移关系、区分检索相关性和证据准入，再制作透明的人审 v2 展示。这是工作流和证据整理改进，不是新的算法指标。

## 模型、延迟、成本与发布安全

历史记录中曾有一次真实 Qwen planning response，当前网页不现场重用或伪称实时。没有可报告的公开 Qwen 延迟、Token 或成本；公网 Qwen 调用关闭。真实 Upstash 隔离验收检查了原子预留、预算、并发、幂等、持久化和故障关闭。剩余问题是未知模型结果可能长期占用并发槽；过早释放会产生并发超限风险。¥5 公网预算预留与已用尽的本地 5/5 开发账本相互独立，也不等同于模型服务商账单硬上限。

## Roadmap

1. Safely recover abandoned concurrency slots without releasing capacity while a model request may still be running; test conservatively, then repeat Cloud security review.
2. Add independent labeled English, non-transfer and cross-domain cases; adjudicate the pending NLP label in a new freeze.
3. Measure Actionable Research Plan Completion with researcher tasks before claiming user value.
4. Validate responsive behavior at narrow desktop and mobile widths; the portfolio captures document the 1440×900 desktop viewport.

## 当前可声明的交付

Online rule-based MVP, OpenAlex retrieval, human-curated Golden Case v2, frozen single-case evaluation, CI success, local isolated Redis safety acceptance, and genuine 1440×900 browser viewport captures. Not yet evidenced: public Qwen operation, user growth, task efficiency gain, commercial revenue or broad search-quality generalization.
