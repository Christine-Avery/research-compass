# Bad Case 001：控制理论中的 NN → GP 探索失败

## 历史记录保护

- [original_trace.json](./original_trace.json) 是用户导出的原始运行记录，只读保存；本案例不修改或覆盖它。
- 原始文件 SHA-256：`42245808de0b10663652a8d2f28cd27458e4a7aba00c57d78134586e7ef09658`。
- JSON 可解析，包含原始兴趣、结构化意图、两条新方案查询及其排序、十篇去重论文、生成的版图/证据/问题，以及四条 Day 1 Baseline 查询及其排序、十三篇去重论文。
- [expected_intent.json](./expected_intent.json) 是**新增的人工标注**，不回写原始 Trace。

## 实际观察（来自原始 Trace 与当前代码）

1. 原始兴趣讨论控制理论中神经网络与高斯过程的区别，希望从已有 NN 文章获得启发，用于 GP 相关研究。Trace 的 `intent.theme` 却是整段原句，`intent.approach` 为空，`goal` 为 `methods`。
2. Trace 的 `intent.constraints` 为“低数据量，安全性”，但这两个词不在原始兴趣中。仅凭 Trace 无法确定用户在澄清表单中如何输入或理解这两个词。
3. 新方案仅检索 `techniques` 和 `evaluation`。两条查询都包含整段中文原句、泛化英文后缀和上述约束；Day 1 Baseline 的四条查询同样保留了整段原句。两套检索均为 `live`，返回的是真实 OpenAlex 记录。
4. 新方案排序第一篇是 [太阳风暴论文](https://openalex.org/W4255073332)，第二篇是 [艺术理论著作](https://openalex.org/W7207844290)；`evaluation` 第一篇是 [复杂网络社区检测综述](https://openalex.org/W4416399009)。标题与本案例的目标探索明显不符。新方案十篇论文的标题和摘要均未出现“高斯过程”或 `Gaussian process`；两篇出现“神经网络”。
5. 生成结果中，研究现状摘录来自 AI 伦理、AI 文本检测和政府文档监测；局限摘录来自艺术理论与 AI 伦理。摘录文本确实存在于对应摘要，但与控制理论 NN → GP 的意图不匹配。两条候选问题引用了这些论文。
6. `ranked_results` 与每条查询的 `returned_ids` 顺序一致，排名为 1–5；原始排序本身未丢失。问题在查询与证据相关性，而非排名序列化缺失。

## 人工判断（不是系统运行事实）

- 预期应识别三个概念：**Control Theory、Neural Networks、Gaussian Processes**，以及从 **NN 文献 → GP 研究** 的思路迁移关系。
- “低数据量”“安全性”不应被当作原始兴趣明确提出的硬约束。若用户另有偏好，需要单独确认其含义与优先级。
- 当前样本不足以断言 NN 或 GP 在某一具体控制问题上的优劣，也不足以宣称存在未研究的空白。

## 待验证根因与修复优先级

| 优先级 | 环节 / 函数 | 当前机制与本案例的关系 | 下一步验证或修复 |
| --- | --- | --- | --- |
| P0 | [`suggest_components`](../../../research_compass/planning.py) | 仅按英文 `for/in/using` 拆分；中文长句未拆出三个概念与 NN → GP 关系，整句成为 `theme`。 | 用本案例做固定样例，抽取领域、两个方法、比较目标和迁移方向；保留用户可修改字段。 |
| P0 | [`build_planned_branches`](../../../research_compass/planning.py) | 把长句、泛化英文词和约束直接拼接，未形成 NN、GP、对照与迁移的专门检索式。 | 生成简短可解释的中英文概念查询，分开检索 NN 控制、GP 控制、比较与迁移。继续保留 Day 1 Baseline。 |
| P0 | [`build_report`](../../../research_compass/evidence.py) / [`_quote`](../../../research_compass/evidence.py) | 只检查是否真实、摘要长度及提示词；没有主题相关性门槛，导致艺术与伦理论文进入现状、局限和 RQ。 | 增加 Evidence Gate：至少验证领域与方法的主题关联；不足时停止生成 RQ，显示“相关证据不足”。 |
| P1 | [`search_papers`](../../../research_compass/retrieval.py) | 仅要求 OpenAlex `has_abstract=True`，按返回顺序展示；没有针对预期概念的相关性过滤或重排。 | 保留原始返回排名，同时记录相关性判断、排除理由与展示排序；用人工标注检验误排。 |
| P1 | [`_sentences`](../../../research_compass/evidence.py) / `LIMITATION_CUE` | 英文标点分句规则不适配中英混合摘要；艺术理论摘录长达 486 字符，关键词命中不代表与用户意图相关。 | 加入中英文分句及局限语境检查，限定引文范围，测试跨语言误命中。 |
| P1 | 澄清输入 / `ResearchIntent.constraints` | Trace 保留了约束值，却没有记录该值在原始兴趣、表单输入与确认硬约束之间的来源和强度。 | 为约束增加来源与确认状态；没有明确确认时只作可选探索维度。 |

以上根因是根据单个 Bad Case 与代码路径提出的**待验证解释**；本轮没有更改检索、意图或证据算法。
