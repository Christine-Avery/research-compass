# Research Compass：V0 / V1 人工标注评测

## 数据与完整性

本报告只分析 `labels_snapshot.csv`，它是 `evaluation/runs/v3_20261014/human_labels.csv` 的只读副本。两者在分析时的 SHA-256 均为 `00168b25e1c614bb9a53b6349a99bb177f145adcf16354b989322e7fe770b0aa`。原始 Trace 和检索 CSV 未修改。逐条结果见 `metrics.json`；复算程序见 `../../analyze_human_review.py`。

这是一条用户意图、一次真实检索快照：V0 有 4 个分支、20 条分支内结果、13 个唯一论文 ID；V1 有 3 个分支、15 条分支内结果、15 个唯一论文 ID。相同论文在不同分支视作独立判断。

| 标注状态 | 数量 | 分母 |
| --- | ---: | ---: |
| 相关性 0/1/2 已填写 | 35 | 35 |
| Evidence Generation 准入 是/否已填写 | 34 | 35 |
| 两项均完成 | 34 | 35 |
| Evidence Generation 准入仍为空 | 1 | 35 |
| 明确标记跳过 | 0 | 35 |

唯一未完成的是 V1 `comparison_transfer` 原始第 5 名 [W2913473169](https://openalex.org/W2913473169)：相关性已标 0，准入为空，`review_status=in_progress`。所有排名指标可使用全部 35 条相关性评分；涉及人工准入的混淆统计只能使用 34 条已填准入的数据，其中 V1 为 14/15。没有自动补标签，空值不视为“否”。

## 指标定义与结果

- **Precision@5**：每个分支按 `raw_rank` 排序，相关性 **1 或 2** 计相关，分母固定为该分支前 5 条；版本结果是完整标注分支的算术平均。本快照所有分支均有 5 条且相关性已填。
- **nDCG@5**：按同一原始顺序、等级增益 `2^relevance - 1`（0、1、3）计算，再除以该分支这 5 条的理想 DCG；无相关结果的分支记 0；版本结果为分支算术平均。理想排序仅在已检出的前 5 条内部形成，不能衡量漏检的论文。
- **无关证据率**：系统标为 `Evidence Eligible` 且人工相关性已填的条目中，人工相关性为 0 的比例。衡量系统准入后的主题污染，不等同于事实性声明支持率。
- **误收录 / 误拒绝**：系统 `Evidence Eligible` 与人工“准入 是/否”比较。分别指系统准入而人工否、系统未准入而人工是；只用人工准入已填的条目。下文另给相关性一致的误拒绝数。

| 方案 | Precision@5 | nDCG@5 | 无关证据率 | 误收录 | 误拒绝 |
| --- | ---: | ---: | ---: | ---: | ---: |
| V0 原始规则 | 0.05（1/20；4 分支） | 0.1077（4 分支平均） | 不适用（系统准入 0 条） | 不适用（无 Evidence Gate） | 不适用（无 Evidence Gate） |
| V1 优化规则 | 0.80（12/15；3 分支） | 0.8210（3 分支平均） | 0%（0/8） | 0（系统准入 8 条，人工准入均为是） | 6（V1 人工准入已填 14 条；人工“是”共 14 条） |

V1 的 6 条原始误拒绝中，**4 条相关性为 1 或 2**，分母为 12 条“人工相关且人工准入是”的 V1 记录，故相关性一致的漏收为 **4/12**。余下 2 条被标为相关性 0、人工准入是，存在标注冲突；不能据此直接放宽 Evidence Gate。V0 没有系统 Evidence Gate，不能把其 19 条相关性 0 的检索结果称作“错误准入”。

| 分支 | 原始排名的相关性 | Precision@5 | nDCG@5 |
| --- | --- | ---: | ---: |
| V0 `overview` | 0, 0, 0, 0, 0 | 0 | 0 |
| V0 `methods` | 0, 0, 0, 0, 0 | 0 | 0 |
| V0 `applications` | 0, 0, 0, 0, 0 | 0 | 0 |
| V0 `challenges` | 0, 0, 0, 1, 0 | 0.20 | 0.4307 |
| V1 `source_method` | 1, 1, 2, 2, 2 | 1.00 | 0.7744 |
| V1 `target_method` | 2, 2, 2, 2, 2 | 1.00 | 1.0000 |
| V1 `comparison_transfer` | 1, 0, 2, 0, 0 | 0.40 | 0.6885 |

**判断：**在这一条查询、这一份检索快照和现有人工标签下，V1 排序确实优于 V0，Precision@5 提高 0.75，nDCG@5 提高约 0.7133。由于版本分支数量及语义不同、样本仅一条用户查询，不能声称总体或统计显著提升，也不能把该结果归功于单一组件。

## 误收录、漏收与跨领域论文

V1 **没有**人工相关性 0 且系统 `Evidence Eligible` 的论文（0/8），也没有“系统准入、人工准入否”的记录。V1 `comparison_transfer` 原始第 2、4、5 名虽为无关论文，系统均保留为 `Retrieved`、未让其进入证据。第 2 名 [A Primer on Neural Network Models for Natural Language Processing](https://openalex.org/W1888026739) 属 NLP，第 4 名 [Deep Neural Network Approximation Theory](https://openalex.org/W2910155483) 缺控制理论与 GP 迁移关联，第 5 名 [Scaling Limits of Wide Neural Networks with Weight Sharing](https://openalex.org/W2913473169) 缺控制理论关联。第 2、4 名同时被人工标为“相关性 0、证据准入是”，应复核准入定义；第 5 名准入未填。

V0 的明显无关论文主要是**检索污染**，不是证据准入错误，例如翻译操纵 [W4244482171](https://openalex.org/W4244482171)、太阳风暴 [W4255073332](https://openalex.org/W4255073332)、艺术理论 [W7207844290](https://openalex.org/W7207844290)。V0 共 19/20 条相关性 0，其中 12 条又被人工标为准入是。这些自相矛盾的人工判断需要复核，不能用来反推 V0 曾生成了有效证据。

V1 的关键漏收如下（均是系统 `Retrieved`、人工准入是）：

| 论文及原始排名 | 人工相关性 | 观察与处理 |
| --- | ---: | --- |
| `target_method` #4 [Learning and Control Using Gaussian Processes](https://openalex.org/W2798274031) | 2 | 摘要涉及 GP、闭环/滚动时域控制；直接相关，优先检查领域术语识别。 |
| `target_method` #5 [Cautious Model Predictive Control Using Gaussian Process Regression](https://openalex.org/W2619551236) | 2 | 摘要涉及 GP、MPC、非线性动力系统；直接相关，优先检查领域术语识别。 |
| `comparison_transfer` #1 [Gaussian Process Regression Networks](https://openalex.org/W1545951971) | 1 | NN 与 GP 的方法桥梁，可作跨领域灵感；摘要应用不在控制理论，作为直接控制领域证据须限制声明范围。 |
| `comparison_transfer` #3 [Phase-functioned neural networks for character control](https://openalex.org/W2611706523) | 2 | 摘要是角色运动/图形动画，未体现 GP；可能是跨领域灵感，不应仅凭“control”当作控制理论中 NN→GP 的直接证据。建议人工复核 2 分及准入用途。 |

另两条形式上的误拒绝就是上述相关性 0、准入是的 NLP 与 NN 近似理论论文。它们应先交由人工复核，而非判定为 Gate 漏收。以上判断基于快照里的标题、摘要及已有人工标注，未核验全文。

## 修复优先级

**先修 Evidence Gate 的漏收，再改 Query Planning。** `target_method` 已把两篇高度相关的 GP 控制论文检出，但 Gate 因摘要没有匹配有限的领域别名而拒绝；扩充并测试 *model predictive control*、*closed-loop control*、*receding horizon control* 等控制术语，以及针对不同分支的准入条件，可直接恢复已检得的有效证据，同时保持目前 0/8 的无关准入水平。此改动应先用这份冻结快照做回归，再重新做真人复核。

随后针对 `comparison_transfer` 改查询规划：该分支仅 2/5 相关，且第 2、4、5 名偏离控制理论或迁移任务。需要更明确地表达 NN→GP 的比较/迁移目标，检索相关方法桥梁与目标领域文献，并在展示中区分跨领域启发和直接领域证据。先复核上文冲突标注及未完成的第 5 条，再评估 Gate 改动的误收录/误拒绝，不自动更改历史标签。

## 复现

在项目根目录运行（输出到新文件，保留本报告的原始输入和结果）：

```powershell
.\.venv\Scripts\python.exe evaluation\analyze_human_review.py evaluation\reports\human_review_v0_v1_20261014\labels_snapshot.csv --output evaluation\reports\human_review_v0_v1_20261014\metrics_recomputed.json
```

检查 `input_sha256` 是否等于上述快照哈希，然后比较 `metrics_recomputed.json` 与 `metrics.json`。程序只读取快照；不调用 Qwen、OpenAlex 或其他付费服务。
