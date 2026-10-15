# Research Compass：Rules V1 vs Qwen V2 增量价值对照实验

> 在 16 条冻结合成研究需求中，11 条形成双方完整实时检索配对。基于机器辅助相关性初评，Qwen V2 的平均 P@5 为 0.836，高于 Rules V1 的 0.636；nDCG@5 为 0.905，高于 Rules V1 的 0.717。但 Qwen 对结构化来源/目标方法关系的保留表现较弱，且端到端时延明显更高。结果支持继续评估选择性 LLM 调用，而非全面替换规则工作流。

**Evaluation type:** Exploratory paired evaluation · **Query source:** Synthetic research needs · **Relevance labels:** Machine-assisted provisional · **Manual adjudication:** Not completed · **Successful paired coverage:** 11/16 · **Production impact:** None

Dataset SHA-256: `dfb37d8b2dd98a93e13c18e9f225d5ae8952def2d285e018b56407ae26a4ba6c`. The frozen inputs, paired traces, labels, original metrics and manifests remain preserved. `audit_recalculate.py` independently recalculates from the run JSONL and label CSV and writes `audit_recalculation.json`; it does not overwrite the original `metrics.json`.

## 1. Why LLM

Rules V1 already turns known concepts and relationships into structured paths and English search queries. The product question was whether Qwen adds enough intent interpretation and query specificity on unseen, ambiguous or cross-domain requests to justify additional latency and token cost. This evaluation isolates planning: both groups use the same input, OpenAlex interface, retrieval workflow and post-retrieval ranking/filtering code.

## 2. Experimental design

- **A:** frozen user input → Rules V1 intent parsing and branch planning → preselected path → OpenAlex → shared post-processing.
- **B:** the same input → fixed Qwen prompt/configuration and schema validation → preselected path → the same OpenAlex and post-processing.
- The 16 newly authored synthetic needs are frozen at four each in S1 explicit, S2 relational, S3 ambiguous/constraint-rich and S4 cross-domain long-tail. They are not interview records and do not reuse the historical Golden Case.
- OpenAlex requests use `has_abstract:true` and `per-page=5`. Traces preserve generated queries, actual request parameters, returned paper IDs, titles, abstracts, links and the five displayed results. No failed case was replaced with another path.
- P@5 counts grades ≥1 as relevant. nDCG uses gain `2^grade−1` and discount `log2(rank+1)`. Main comparisons include only records with a live preselected-path Top 5 from both systems. The route selector was fixed before relevance scoring.
- Prompt/model parameters remained fixed. The experiment-only ledger kept new API usage separate from the historic ledger; there was no Redis or public Qwen setting change.

## 3. Main results

**Independent recalculation passed** for the main paired values, paired win/tie counts and denominators: all 11 comparisons against the existing `metrics.json` agree within 1e-12 (counts exact). The recomputed per-query DCG, IDCG, nDCG, group results and consistency checks are in `audit_recalculation.json`.

| Metric (11 complete pairs) | Rules V1 | Qwen V2 | Qwen − Rules |
|---|---:|---:|---:|
| Mean Precision@5 | 0.636 | 0.836 | +0.200 |
| Mean nDCG@5 | 0.717 | 0.905 | +0.188 |

nDCG wins/ties/losses for Qwen: **9/2/0**. P@5 wins/ties/losses: **4/6/1**. Paired bootstrap 95% intervals from the original metric report were ΔP@5 [0.000, 0.436] and ΔnDCG@5 [0.064, 0.367]. With only 11 pairs these intervals are unstable and do not establish statistical significance.

## 4. Results by query type

| Type | Complete pairs | Rules P@5 / nDCG@5 | Qwen P@5 / nDCG@5 | ΔP@5 / ΔnDCG@5 |
|---|---:|---:|---:|---:|
| S1 explicit | 4 | 0.950 / 0.826 | 1.000 / 0.978 | +0.050 / +0.151 |
| S2 relational | 3 | 0.733 / 0.662 | 0.667 / 0.807 | −0.067 / +0.145 |
| S3 ambiguous | 4 | 0.250 / 0.649 | 0.800 / 0.906 | +0.550 / +0.257 |
| S4 long-tail | 0 | — | — | Not measurable |

S4 contains four frozen requests but none formed a complete A/B pair. These results cannot establish long-tail performance.

## 5. Intent preservation

| Field | Rules V1 | Qwen V2 |
|---|---:|---:|
| Explicit domain | 10/16 | 15/16 |
| Research goal (semantic audit) | 5/16 | 11/16 |
| Source method, applicable cases | 4/8 | 1/8 |
| Target method, applicable cases | 8/14 | 7/14 |
| Source/target direction, applicable cases | 3/8 | 0/8 |
| No invented hard constraints | 16/16 | 15/16 |
| All applicable fields correct per query | 2/16 | 7/16 |

Direction trace audit: in seven of eight applicable cases, the saved raw Qwen response contains source, target and relationship values; the eighth is S4-02, where Qwen returned no valid response. The parsed intent still preserves the full expected structured relation in 0/8. Several emitted method strings are expanded or normalized differently from the frozen terms, and the parser/selector drops or fails to recognize fields. The available trace does not establish for every case whether the underlying semantic direction was correct, so those causes remain **not fully confirmed**; they must not be represented as eight proven model reasoning errors.

## 6. Latency and cost

- End-to-end median latency: **Rules 1.59 s**, **Qwen 19.81 s**. Means were 1.36 s and 20.65 s respectively, including planning/retrieval/failure outcomes represented in the run data.
- Successful Qwen usage: 15 plans, 4,155 input tokens and 8,729 output tokens. At the recorded ¥0.8/M input and ¥2.7/M output rates, known estimated spend was **¥0.026892** total, about **¥0.001793 per successful request**.
- There were 17 Qwen attempts with unknown usage: 16 first-run sandbox network failures and one failed request in the completed run. Their combined per-call reservation upper bound is **¥0.14382**. Known estimated cost plus that upper bound is **¥0.1707123**, not a confirmed invoice amount.
- The client does not automatically retry. The 16-call completed run was a separate rerun after the first-run local ledger-writer defect was found and fixed. The historical ledger was restored and its before/after hashes match; the experiment uses its own ledger. No Redis or public Qwen switches were changed.

## 7. Completeness, route-selection bias and failures

The independent audit found 16 unique frozen cases, 16 corresponding run records, 119 unique query-paper labels, no duplicate query-paper label keys, no missing labels for Top-5 items, no duplicate IDs within Top 5, and no Top-5 IDs absent from the recorded OpenAlex responses. All 119 labels are marked AI-assisted and pending human review. The frozen hash and all unchanged raw-output hashes match their manifests. The original `run_manifest.json` still records the previous generated `RESULTS.md` hash; that one mismatch is expected because this archival round rewrote the report, and the historical manifest was not edited.

Five cases lack a complete pair:

| Query | A / Rules | B / Qwen | Recorded reason |
|---|---|---|---|
| S2-02 | Live Top 5 | No retrieval | Qwen planned three branches and the API succeeded, but the relation selector found no matching branch. |
| S4-01 | No retrieval | No retrieval | Neither planner output matched the relation selector. |
| S4-02 | No retrieval | Planner error | Rules had no matching path; Qwen timed out with usage unknown, with no automatic retry. |
| S4-03 | No retrieval | Live Top 5 | Rules had no matching path; Qwen had a selected path. This one-sided result is excluded from paired metrics. |
| S4-04 | No retrieval | No retrieval | Rules had no matching path; Qwen generated branches but the relation selector found none. |

The pre-registered description specified the highest semantic match, but the implementation chooses the **first generated branch containing a relationship cue**, not a scored highest semantic match. A branch purpose can cause an otherwise non-primary path to be selected. This is an implementation deviation and limits interpretation; it was not corrected after viewing relevance results, and neither group was rerouted for scoring.

The first sandbox attempt also exposed an experiment-ledger path bug. Its failed-attempt log is retained, and the historic ledger hash was restored to the pre-run value; the completed rerun is separately represented in the paired traces and experiment ledger. The ledger has 32 requests: 16 first-run network errors and 16 completed-run calls (15 successes, one timeout). There were **no automatic retries**; the full experiment was rerun after the ledger defect was fixed. All 17 failed calls have unknown usage and remain in cost accounting.

## 8. Bad-case analysis

- **Qwen clearly better on provisional nDCG — S3-02:** Rules parsed only the broad Medical Imaging domain and searched `Medical Imaging` (P@5 0.00, nDCG@5 0.00). Qwen parsed a semi-supervised medical image segmentation task and searched uncertainty estimation with limited labels (1.00, 1.00). The five Qwen results were all grade 2; Rules returned broad medical-imaging titles. Likely difference layer: ambiguous-goal interpretation and English query planning. Labels remain provisional.
- **Qwen better — S1-03:** Rules queried `Medical Imaging convolutional neural networks` (0.80, 0.703); Qwen narrowed the query to small-lesion segmentation and boundary precision (1.00, 1.000). Difference layer: task specificity/query planning; same OpenAlex source and ranking.
- **Rules better on P@5 — S2-03:** Rules returned P@5 1.00 versus Qwen 0.80; Qwen nevertheless had higher nDCG (0.941 vs 0.848). This is a mixed ranking/recall case, not evidence of an overall Rules win on nDCG.
- **Close — S1-04:** Both systems scored P@5 1.00 and nDCG@5 1.00, using different query formulations and retrieving provisional-relevant materials.

No complete pair showed a Rules nDCG win. This is a description of this small provisional sample only. The selector and source coverage can also affect outcomes; no model-only causal attribution is possible for every case.

## 9. Evaluation status and reproducibility

The 119 relevance records contain score, rationale, cited abstract excerpt, AI-assistance provenance and human-review status. The labels are **machine-assisted provisional**, not double-blind, independently adjudicated or a human gold standard. This round did not complete manual adjudication. The audit independently recalculates per-query P@5, DCG, IDCG and nDCG from the paired JSONL and label CSV, compares summary values against the unchanged original `metrics.json`, and reports integrity checks in `audit_recalculation.json`.

Reproduce the offline audit with:

```powershell
python evaluation/llm_vs_rules_v1/audit_recalculate.py
```

The included audit script recalculates the archived metrics without network access. Regenerating model outputs would require a separate local API setup and would make external calls; it was not part of this archive round. No new Qwen or OpenAlex request was made. Inspect `freeze_manifest.json`, `run_manifest.json`, `paired_runs.jsonl`, `qwen_experiment_ledger.json` and `relevance_labels.csv` for provenance.

## 10. Product decision

Recommendation: **Rules-first + Selective LLM**. Keep Rules V1 as the fast, low-cost default and fallback. Evaluate optional Qwen planning for ambiguous, multi-constraint or vocabulary-crossing requests, but require users to confirm the plan and validate source/target relations before retrieval. The observed provisional retrieval advantage is promising, especially on S3; the 19.8-second median and direction-field loss argue against replacing Rules wholesale. Expand use only after human label review and representative task validation show that quality gains justify latency and cost.

## 11. Limitations

- All 16 requests are synthetic, with four cases per type; they do not represent a sampled user population.
- Machine-assisted relevance labels await human sampling/adjudication. Current quality scores are provisional.
- Only 11/16 requests form a complete pair, and S4 has zero complete pairs.
- The route selector implementation diverged from the preregistered highest-semantic-match wording.
- OpenAlex coverage/ranking and query matching affect results; the test does not establish end-to-end research-task completion or causal quality gain.
- Qwen calls have substantial additional latency, one timeout in the completed run, and unknown usage for 17 failed attempts across the initial and completed runs.
- No new experiment call was made in this archive/release round. **Production impact: None.**
