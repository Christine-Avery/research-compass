# Golden Case v2 · Opportunity Cards 证据审计（已获人工确认）

本审计只使用冻结的 [OpenAlex 检索快照](../evaluation/runs/v3_20261014/live_openalex_golden.json)、[最终人工裁定](../evaluation/freeze/final_20261014/final_adjudication.csv)和[裁定说明](../evaluation/freeze/final_20261014/adjudication.json)。这是 **2026-10-14 保存的摘要级证据**，不是全文核验或新一轮实时检索。审计获用户确认后，另建[独立 v2 卡片快照](../evaluation/cases/badcase_001/golden_case_v2.json)；尚未推送或发布。

核对结果：V1 有 3 个分支、15 条论文；冻结裁定中的 15 个 OpenAlex ID、标题和摘要与检索快照逐项一致。NN 来源分支 5 条、GP 目标分支 3 条被系统标为 `Evidence Eligible` 且人工准入为 `yes`；迁移比较分支没有一条通过 Evidence Gate。相关性高不等于适合当前 Evidence Generation。以下“支持”只表示摘要明确表述，不代表全文或独立复现实验已核验。

## A · 稳定性理论与安全验证

| 分类 | 可使用的表述与依据 |
| --- | --- |
| 摘要直接支持的事实 | NN 来源：[NLq theory](https://openalex.org/W2406620654)（`Evidence Eligible`，人工 `yes`）的摘要称该理论源于神经状态空间控制系统的稳定性准则，并给出全局渐近稳定、输入输出稳定和耗散性的充分条件。GP 目标：[Safe learning of regions of attraction](https://openalex.org/W2298163601)（`Evidence Eligible`，人工 `yes`）摘要描述基于 GP 先验、Lyapunov 函数和高概率稳定区域的安全探索；[Distributed Gaussian Processes](https://openalex.org/W4295046714)（`Evidence Eligible`，人工 `yes`）摘要称用 Lyapunov 理论分析所提多智能体跟踪控制律的稳定性。 |
| 基于文献的推断 | NN 与 GP 控制文献都使用稳定性分析，但前述论文针对不同系统、假设和保证类型。可比较各自的证书、假设和不确定性处理方式；不能将其结论视为可直接互换。 |
| 待验证研究假设 | NN 控制的稳定性分析思路能否启发带 GP 模型不确定性的控制器设计或证明？必须先明确控制对象、误差假设与保证类型，再检索并验证。 |
| 缺失证据 | 冻结结果中没有通过 Gate 的论文直接证明 NN→GP 稳定性理论迁移；不能宣称现有研究没有做过。安全保证也不是原始用户输入的硬约束。 |

## B · 在线学习、数据选择与 GP 模型更新

| 分类 | 可使用的表述与依据 |
| --- | --- |
| 摘要直接支持的事实 | GP 目标：[Gaussian Processes for Data-Efficient Learning](https://openalex.org/W2018705428)（`Evidence Eligible`，人工 `yes`）摘要称通过 GP 转移模型、模型不确定性及控制器学习提高数据利用效率；[Distributed Gaussian Processes](https://openalex.org/W4295046714)（`Evidence Eligible`，人工 `yes`）摘要描述多智能体 GP 模型的分布式聚合。另有 [Learning and Control Using Gaussian Processes](https://openalex.org/W2798274031) 摘要明确提及信息性数据选择、更新已有 GP 模型及闭环在线改进，**但它的系统状态仅为 `Retrieved`，最终人工准入为 `no`，只能列为阅读/再检索线索**。 |
| 基于文献的推断 | 数据选择和持续更新可能是 GP 控制的有用探索轴；分布式聚合与在线更新并非同一个已证实的方法。 |
| 待验证研究假设 | 是否能从 NN 控制的在线学习或样本选择方法迁移出适用于 GP 模型更新的策略，并在相同控制任务中检验数据效率、计算代价与稳定性？ |
| 缺失证据 | 已准入的 NN 来源论文没有摘要明确研究“在线学习/数据选择”的相应方法。[A computational field theory](https://openalex.org/W2205893158)虽谈 NN 的自适应控制，却不支持具体数据选择机制。当前缺少可核验的 NN→GP 方法桥梁；最直接的 GP 在线更新论文也未获当前证据准入。 |

## C · NN 结构设计与 GP 表达能力

| 分类 | 可使用的表述与依据 |
| --- | --- |
| 摘要直接支持的事实 | NN 来源：[Theory and applications of neural networks for industrial control systems](https://openalex.org/W2156562940)（`Evidence Eligible`，人工 `yes`）摘要谈到循环网络、前馈网络和控制应用。跨方法阅读线索：[Gaussian Process Regression Networks](https://openalex.org/W1545951971) 摘要描述结合贝叶斯 NN 结构特征与 GP 灵活性；[Scaling Limits of Wide Neural Networks](https://openalex.org/W2913473169) 摘要讨论若干宽 NN 架构的 GP 极限。**后两篇均为 `Retrieved`、人工相关性 0、准入 `no`，不属于当前控制研究版图的生成证据。** |
| 基于文献的推断 | NN 架构与 GP 表达形式之间存在可进一步检索的理论联系；现有摘要不能推出某种架构能改善 GP 控制表现。 |
| 待验证研究假设 | 某种经过具体定义的 NN 特征表示或结构先验，能否用于 GP 控制模型并改善目标任务的表达能力？需先确定架构、GP 构造与控制基准。 |
| 缺失证据 | 冻结结果中缺少通过 Gate 的“NN 结构 → GP 控制表达能力”论文，也缺少相应控制应用验证。[Phase-functioned neural networks](https://openalex.org/W2611706523)研究游戏/虚拟角色运动，人工准入 `no`，不能替代控制系统证据。C 目前只能是探索路径。 |

## 来源及标注冲突

- [Learning and Control Using Gaussian Processes](https://openalex.org/W2798274031) 与 [Cautious Model Predictive Control](https://openalex.org/W2619551236) 的人工相关性均为 2，但用户最终接受“摘要不准入当前 Evidence Generation”；卡片中可作为阅读或下一轮检索线索，不能作为已准入的主证据。
- [A Primer on Neural Network Models for Natural Language Processing](https://openalex.org/W1888026739) 的历史标签为相关性 2、准入 `yes`，但复核理由称其未涉及控制理论；[最终裁定](../evaluation/freeze/final_20261014/adjudication.json)仍标记 `pending_user_decision`。v2 三张卡片均不应使用该论文作证据。
- [Distributed Gaussian Processes](https://openalex.org/W4295046714) 在冻结 CSV 的人工 `evidence_reason` 误写为“神经网络在控制理论的应用”；论文标题与摘要实际为 GP 多智能体控制。其 ID、标题和摘要与快照一致，卡片应按 GP 目标文献归类，并保留该注释不一致的审计记录。
- 迁移比较分支 5/5 均未通过 Evidence Gate；没有已准入的直接 NN→GP 迁移证明。三张卡片应显著标为 **Human-curated Golden Case v2 Snapshot / 待验证研究假设**，不能表现成实时 Qwen 结论或已发现的研究空白。

**已批准的呈现边界：** A 用摘要事实建立两侧对照，B 只以 GP 侧事实加缺失 NN 来源的探索问题呈现，C 仅以结构/表达的待验证假设呈现。独立 v2 快照与 Page 3 按这些边界展示。
