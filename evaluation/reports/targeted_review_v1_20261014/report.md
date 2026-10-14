# Research Compass：定向标注复核报告

**状态：最终版：7 条均经人工复核，准入标签已填满。**

原始 `human_labels.csv` 保持只读；人工复核事件另存，首次保存时建立 `human_labels_reviewed.csv`。未复核条目沿用历史值，缺失准入不补填。原始检索 Trace 和系统 `rule_status` 均未改变。

定向条目：已复核 7/7；V1 人工准入已填 15/15。全部 35 条相关性均已标注；V0 的 20 条不在本轮复核范围。

## 指标定义与分母

- 相关性 ≥1 算命中。Precision@5 分母为每分支前 5 条；版本结果是完整标注分支的宏平均。V0 为 4 分支 / 20 条，V1 为 3 分支 / 15 条。
- nDCG@5 使用人工等级 0/1/2 对应增益 0/1/3，按原始排名计算，每分支以该分支前 5 条的理想排序归一化，再对分支宏平均。
- 无关证据率 = 系统 `Evidence Eligible` 中人工相关性为 0 的条数 / 系统准入且已标相关性的条数。V0 没有 Evidence Gate，记 N/A。
- Gate TP/FP/FN/TN 只纳入已填人工准入 yes/no 的 V1 记录。Precision = TP/(TP+FP)，Recall = TP/(TP+FN)；分母为 0 时 N/A。误收录 = FP，误拒绝 = FN。未填准入排除而不视为 no。
- 评测负样本保留在检索评测集中，用于衡量排除能力；它并不因此适合进入 Evidence Generation。相关性和摘要支持性分别人工判断。

## V0 / V1 修正版结果

| 方案 | Precision@5 | nDCG@5 | 无关证据率 | 误收录 FP | 误拒绝 FN | Gate Precision | Gate Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V0 历史 | 0.0500 (1/20) | 0.1077 (4 分支) | N/A | N/A | N/A | N/A | N/A |
| V1 修正版 | 0.8000 (12/15) | 0.8111 (3 分支) | 0/8 (0.00%) | 0 | 3 | 8/8 (100.00%) | 8/11 (72.73%) |

V1 Gate 混淆计数：TP=8、FP=0、FN=3、TN=4；分母为 15 条已填人工准入的 V1 记录。

## 标签修正造成的变化（历史 → 修正）

| 指标 | 历史 | 修正 | 变化 |
| --- | ---: | ---: | ---: |
| V1 Precision@5 | 0.8000 | 0.8000 | +0.0000 |
| V1 nDCG@5 | 0.8210 | 0.8111 | -0.0098 |
| V1 无关证据率 | 0/8 | 0/8 | +0.0000 |
| V1 误收录 FP | 0 | 0 | +0 |
| V1 误拒绝 FN | 6 | 3 | -3 |
| V1 Gate Precision | 8/8 (100.00%) | 8/8 (100.00%) | +0.0000 |
| V1 Gate Recall | 8/14 (57.14%) | 8/11 (72.73%) | +0.1558 |

历史准入缺 1 条，因此历史 Gate 指标使用 14/15 条；修正列按当前已填数量计算，若仍缺失同样属于阶段性数值。V0 排名标签未修正，V0 指标无变化。

### 实际改动的人工标签

| 论文 / 分支 / 排名 | 相关性 | 证据准入 |
| --- | --- | --- |
| [Gaussian Process Regression Networks](https://openalex.org/W1545951971) · comparison_transfer #1 | 1 → 0 | yes → no |
| [A Primer on Neural Network Models for Natural Language Processing](https://openalex.org/W1888026739) · comparison_transfer #2 | 0 → 2 | yes → yes |
| [Phase-functioned neural networks for character control](https://openalex.org/W2611706523) · comparison_transfer #3 | 2 → 1 | yes → no |
| [Deep Neural Network Approximation Theory](https://openalex.org/W2910155483) · comparison_transfer #4 | 0 → 0 | yes → no |
| [Scaling Limits of Wide Neural Networks with Weight Sharing: Gaussian Process Behavior, Gradient Independence, and Neural Tangent Kernel Derivation](https://openalex.org/W2913473169) · comparison_transfer #5 | 0 → 0 | 空 → no |

### 复核事件（含原因和 UTC 时间）

- 2026-10-14T08:37:29.473965+00:00 · [https://openalex.org/W2798274031](https://openalex.org/W2798274031) · 相关性 2 → 2；准入 yes → yes；原因：不是完全的神经网络灵感，但是对最终找到和GP相关的方案有启发意义，可以考虑保留。
- 2026-10-14T08:39:26.387070+00:00 · [https://openalex.org/W2619551236](https://openalex.org/W2619551236) · 相关性 2 → 2；准入 yes → yes；原因：虽然不是神经网络在控制领域的应用，但是知道GP在控制领域怎么用也有助于方法迁移。
- 2026-10-14T08:40:48.957811+00:00 · [https://openalex.org/W2913473169](https://openalex.org/W2913473169) · 相关性 0 → 0；准入 空 → no；原因：属于神经网络相关内容，但是和控制理论背景完全无关
- 2026-10-14T08:40:57.555666+00:00 · [https://openalex.org/W2913473169](https://openalex.org/W2913473169) · 相关性 0 → 0；准入 no → no；原因：属于神经网络相关内容，但是和控制理论背景完全无关
- 2026-10-14T08:40:59.630852+00:00 · [https://openalex.org/W2913473169](https://openalex.org/W2913473169) · 相关性 0 → 0；准入 no → no；原因：属于神经网络相关内容，但是和控制理论背景完全无关
- 2026-10-14T08:41:01.608579+00:00 · [https://openalex.org/W2913473169](https://openalex.org/W2913473169) · 相关性 0 → 0；准入 no → no；原因：属于神经网络相关内容，但是和控制理论背景完全无关
- 2026-10-14T08:41:03.853587+00:00 · [https://openalex.org/W2913473169](https://openalex.org/W2913473169) · 相关性 0 → 0；准入 no → no；原因：属于神经网络相关内容，但是和控制理论背景完全无关
- 2026-10-14T08:41:33.525553+00:00 · [https://openalex.org/W2910155483](https://openalex.org/W2910155483) · 相关性 0 → 0；准入 yes → no；原因：和神经网络高度相关但是完全不是控制理论应用场景
- 2026-10-14T08:41:56.676320+00:00 · [https://openalex.org/W2611706523](https://openalex.org/W2611706523) · 相关性 2 → 1；准入 yes → no；原因：属于神经网络在控制理论的应用（还需综合考虑其权威性和时效）
- 2026-10-14T08:42:06.915426+00:00 · [https://openalex.org/W1888026739](https://openalex.org/W1888026739) · 相关性 0 → 2；准入 yes → yes；原因：仅与神经网络有关，未考虑控制理论场景
- 2026-10-14T08:42:22.005981+00:00 · [https://openalex.org/W1545951971](https://openalex.org/W1545951971) · 相关性 1 → 0；准入 yes → no；原因：属于神经网络和高斯过程结合，但是没有考虑应用场景。

## 仍被 Gate 拒绝、但人工标为应准入的论文

- [Learning and Control Using Gaussian Processes](https://openalex.org/W2798274031)：target_method #4，人工相关性 2，系统 Retrieved；目标领域直接漏收候选。 人工理由：属于高斯过程在控制理论的应用（还需综合考虑其权威性和时效）。
- [Cautious Model Predictive Control Using Gaussian Process Regression](https://openalex.org/W2619551236)：target_method #5，人工相关性 2，系统 Retrieved；目标领域直接漏收候选。 人工理由：属于GP在控制理论的应用（还需综合考虑其权威性和时效）。
- [A Primer on Neural Network Models for Natural Language Processing](https://openalex.org/W1888026739)：comparison_transfer #2，人工相关性 2，系统 Retrieved；跨领域 / 迁移边界判断，须复核证据用途。 人工理由：仅与神经网络有关，未考虑控制理论场景。

其中 `target_method` 两篇 GP 控制论文的摘要直接涉及 GP 与控制，是优先修复的 Gate 漏收。`comparison_transfer` 中的 NLP 论文虽被人工改为相关性 2、准入 yes，但复核理由指出仅与神经网络有关、未考虑控制理论场景；它计入上表正式指标中的 FN，同时应单独核对是否真能支持本研究问题，不据此放宽 Gate。

## 修复判断

优先修 Evidence Gate：目标方法分支中已检出的两篇 GP 控制论文仍被拒绝，应先改控制领域术语及准入判断，并用冻结快照检查误收录。其次改 Query Planning：`comparison_transfer` 分支需减少偏离 NN→GP 控制研究目标的结果，并区分跨领域启发与直接证据。NLP 论文的人工评分与理由需单独复核，不能当作改宽 Gate 的依据。该顺序只依据当前单案例，不推断总体效果。

复现：在项目根目录运行 `.\.venv\Scripts\python.exe evaluation\build_targeted_report.py`。脚本仅读取历史标签和人工复核事件，重建修正版 CSV 与报告，不调用 Qwen/OpenAlex。
