# P0 Search Quality Regression Run — 2026-10-14

This run is derived from the immutable `evaluation/cases/badcase_001/original_trace.json` and `expected_intent.json`. It writes only to this run directory. Re-run with:

```powershell
.venv\Scripts\python.exe evaluation\run_p0_snapshot.py
```

## Version meanings

- **V0**: archived Day 1/Day 2 rule output copied into the run artifact without changing the source.
- **V1**: bilingual domain and method term normalization only. It does not assign source/target roles.
- **V2**: structured domain, source method, target method, task, relation, explicit constraints, and intent-specific query branches.
- **V3**: conservative relevance/evidence gate replay over the archived V0 planned candidate pool. It is an offline gate replay, not fresh retrieval and not a new ranking.

## Metrics and adjudication

`metrics.json` records the six gold intent slots and their denominator. The Golden Case has **n=1**. Two other language/topic cases are smoke-test assertions in unit tests, not a human-adjudicated sample. Precision@5, direction coverage, irrelevant evidence rate, and semantic claim-support rate remain null until `human_review.csv` is completed. Rule relevance scores are not labels.

`human_review.csv` is intentionally blank for manual adjudication. For each retrieved paper, set `relevance_label` and `evidence_eligible_label` to `relevant`/`irrelevant` or `yes`/`no`, and annotate claim support where applicable. Record reviewer and notes. Do not use a model's relevance score as the reference label.

`legacy_quote_exact_span_count` checks whether archived quote strings occur verbatim in the archived abstract. This verifies span provenance only; it is **not** semantic Claim Support Rate.

## Current limitations

- The archived trace has no untouched raw OpenAlex response payload, so this replay uses the saved normalized paper records. New live runs now retain raw work records and raw rank.
- A fresh OpenAlex V2 query result is required before comparing Precision@5 and direction coverage fairly.
- The relevance and evidence rules are conservative; false negatives and synonym gaps require manual review.
- No LLM was called and no paid service was used.
