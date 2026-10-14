# Research Compass V3 — Quality and Cost Comparison

Run date: 2026-10-14. Golden source hash verified; original trace remains read-only.

| Strategy | Intent Preservation | Precision@5 | Direction Coverage | Irrelevant Evidence Rate | Latency | Cost / Failure |
|---|---:|---:|---:|---:|---|---|
| V0 · archived rules | 0/7 (n=1 archived case) | 待人工标注 | N/A · no structured directions / gate | 待人工标注 | 6791 ms, 1 Live run (4 queries) | LLM ¥0; OpenAlex no charge recorded<br>0/4 query failures |
| V1 · optimized rules | 21/21 (n=3; hand-authored paired set) | 待人工标注 | 2/3 (provisional gate coverage; 3 branches) | 待人工标注 | 5626 ms, 1 Live run (3 queries); parser avg 2.14 ms | LLM ¥0; OpenAlex no charge recorded<br>0/3 query failures |
| V2 · Qwen planner | N/A · no valid Qwen response | N/A · no V2 retrieval | N/A | N/A | N/A · no successful response | 2 attempted; usage/bill unknown; reserve upper bound ¥0.01692<br>2/2 Qwen request failures (URLError) |
| V3 · hybrid (offline simulation) | 21/21 (n=3; rules fallback this run) | 待人工标注; no separate retrieval | 2/3 inherited from V1 fallback; provisional | 待人工标注 | N/A · routing only; no deployed E2E measurement | Incremental simulation ¥0; deployed hybrid cost unmeasured<br>Qwen unavailable; all routed cases fell back to rules |

## Metric definitions and sample sizes

- **Intent Preservation:** exact matched slots / seven annotated slots per case: domain, exact concept set, source, target, task type, directed relation, explicit constraints. V0 n=1; V1/V3 n=3; V2 n=0 valid responses.
- **Precision@5:** manually labelled relevant records / manually labelled records in each branch's raw ranks 1–5. No percentage is reported while labels are blank.
- **Direction Coverage:** expected Golden directions with at least one Evidence Eligible result / 3 (source, target, comparison/transfer). Automated gate count only; human confirmation is pending.
- **Irrelevant Evidence Rate:** manually judged irrelevant Evidence Eligible papers / all manually judged Evidence Eligible papers. `live_openalex_human_review.csv` has 35 rows and 0 completed labels.
- **Latency:** one live OpenAlex run, including planning plus retrieval for V1; single-run timings are noisy and not a performance claim. Qwen has no successful response latency.
- **Cost:** official Qwen3.8-Flash list price was ¥0.8/M input and ¥2.7/M output tokens. Requests were capped at 4,500 input and 1,800 output tokens: at most ¥0.00846 per request, or ¥0.0423 across the five-call limit. Two failed attempts returned no usage, so actual billing is unknown; ¥0.01692 remains reserved as an upper bound for this run.

## Live retrieval and failures

- OpenAlex key status: loaded (boolean only). V0 returned 13 unique papers in Live mode; V1 returned 15 unique papers in Live mode. V1 rule gate marked 8 branch-ranked candidates Evidence Eligible across 3 branches (source/target/comparison coverage 2/3). These are model gate outputs, not human precision labels.
- V1 did not admit any paper from the combined comparison/transfer branch. The report says evidence is insufficient for that direction; it does not infer a research gap.
- The archived V0 query results include plainly unrelated title/abstract candidates. V0 had no relevance/evidence gate; its 13 unique results are retrievals, not evidence.
- Qwen3.8-Flash network calls: 2 attempted, 2 failed with URLError; no auto-retry; token usage and bill unknown. The cumulative attempt count remains under the hard five-call cap.
- V3 used an input-wording-only routing heuristic in offline simulation (relational cues to Qwen; plain map queries to rules). Since Qwen was unavailable, routed cases fell back to rules. No Qwen quality lift or hybrid deployed cost is established.

## Reproduce

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe evaluation\run_v3_intent_comparison.py
.venv\Scripts\python.exe evaluation\run_v3_live_openalex.py
.venv\Scripts\python.exe evaluation\write_v3_comparison_report.py
```

The Qwen comparison script consumes the bounded Qwen call ledger; do not rerun it after network failure unless intentionally spending another allowed attempt. The Golden Trace is only read and hash-checked.

## Manual review

Fill `live_openalex_human_review.csv` using the actual title and abstract. Label relevance to the intended domain/method/direction, evidence eligibility, and claim support separately. Do not use the rule score as the label.
