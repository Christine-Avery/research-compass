# Evaluation Case Study — Research Compass v1

## Frozen result

The frozen comparison is one Chinese Golden Case about exploring neural-network ideas for Gaussian-process research in control theory. V0 and V1 use different branch sets; these are rule-based versions, not a paired same-query/same-branch experiment and not Qwen V2 results.

| Version | Precision@5 | nDCG@5 |
| --- | ---: | ---: |
| V0 rule baseline | 0.0500 (1/20 judged top-five items; macro-average across 4 branches) | 0.1077 (macro-average across 4 branches) |
| V1 optimized rules | 0.8000 (12/15 judged top-five items; macro-average across 3 branches) | 0.8111 (macro-average across 3 branches) |

Relevance threshold is human label ≥1. nDCG uses graded gains 0/1/3 for labels 0/1/2 and raw rank, normalized per branch before macro averaging. All 35 source rows have relevance judgments. These figures describe this single frozen case only and do not establish statistical significance, general quality improvement, or an LLM uplift.

## Evidence gate adjudication

The corrected V1 gate report contains 15 V1 records: 8 system-admitted and 7 rejected. Among the 15, human evidence eligibility has 11 "yes" and 4 "no" labels; TP=8, FP=0, FN=3, TN=4. Gate Precision = 8/(8+0)=100%; Recall = 8/(8+3)=72.73%. The eligible-label denominator is 15. Irrelevant admitted evidence = 0/8. These values are the frozen adjudicated rule evaluation, not production guarantees.

The two GP control papers at `target_method` ranks 4 and 5 were reviewed by the user as relevant papers whose abstracts were not sufficient for the intended evidence-generation task. This distinguishes **paper relevance** from **abstract evidence eligibility**; their accepted exclusion is not a false rejection. The NLP paper label conflict remains open and is not changed by this report; do not reuse a disputed recall claim without consulting the frozen adjudication artifact.

## Interpretation and limitations

- The historical comparison is not controlled for equivalent branch composition: V0 has overview/methods/applications/challenges; V1 has source method/target method/comparison-transfer.
- The sample is one query and 35 branch-level records, including duplicate papers across branches as separate judgments.
- Ranking metrics do not evaluate missed papers outside the retrieved set.
- Relevance and Evidence Generation eligibility are separate human labels. Eligibility does not prove any particular generated claim is supported.
- Abstract evidence is not full-text verification.
- No claim of Qwen improvement, user growth, or real-user outcome is supported by this case.

## Reproduction sources

- Historical comparison: `evaluation/reports/human_review_v0_v1_20261014/`.
- Human correction event log and report: `evaluation/reports/targeted_review_v1_20261014/`.
- Final adjudication/freeze: `evaluation/freeze/final_20261014/`.
- The source Trace, human labels, correction events and freeze manifest are historical evidence and must remain unchanged.

## Next evaluation

Resolve the NLP judgment with the reviewer, freeze a new adjudication version rather than editing the old one, then add independent English and non-transfer tasks. Keep the same query set, branch-level relevance thresholds, evidence eligibility definitions, and human review protocol across variants. Publish denominators and uncertainty; do not infer an LLM uplift from the current case.
