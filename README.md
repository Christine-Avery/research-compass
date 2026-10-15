# Research Compass

Research Compass helps novice researchers turn a broad interest into a source-grounded next research step. It focuses on **what to search when you do not yet know what to search for**, rather than presenting itself as another paper database.

**Public demo:** [research-compass-ai.streamlit.app](https://research-compass-ai.streamlit.app/). The public app offers V1 rule planning, OpenAlex retrieval, and a clearly labeled historical snapshot. Live public Qwen planning is disabled while its concurrency recovery awaits safety review.

## Product flow

1. **AI Intent Studio** — enter a natural-language interest, optionally clarify one key ambiguity, review and edit the structured intent. The interface distinguishes live Qwen, rule fallback and a historical snapshot.
2. **Research Path Explorer** — compare two or three exploration paths and English queries. Selecting a path triggers OpenAlex retrieval. Results retain OpenAlex IDs, abstracts, original links, rank and relevance explanation.
3. **Evidence & Next Steps** — organize the retrieved abstract evidence, distinguish paper relevance from eligibility for evidence generation, provide candidate questions as hypotheses to verify, and copy a Research Plan Summary.

The public app also has an **opt-in, human-curated Golden Case v2 demonstration**. Page 2 maps the three saved paths to one Page 3 card each: path 1 → A (stability and safety), path 2 → C (NN structure and GP expressiveness), path 3 → B (online learning and GP model updates). Only the selected direction appears. Each card separates admitted abstract evidence, a hypothesis to verify, evidence gaps, and papers kept only as Further Reading. [Open the public Golden Case v2 demo](https://research-compass-ai.streamlit.app/?prototype_snapshot=golden&opportunities=v2). Archived Qwen/OpenAlex data are historical; cards are manually curated and do not measure Qwen quality. An edited card query goes to Page 2 and requires a separate click before live OpenAlex retrieval.

## Architecture

```text
Streamlit pages + session workflow
  ├─ Intent/query planning: Qwen (explicitly gated) or transparent V1 rules
  ├─ Retrieval: PyAlex → OpenAlex API
  ├─ Relevance/evidence gate: existing rule modules and abstract-only evidence
  ├─ Evaluation: frozen traces + human judgments + read-only public view
  └─ Public Qwen budget: Upstash Redis REST EVAL, default disabled
```

Core retrieval uses [PyAlex](https://github.com/J535D165/pyalex) and [OpenAlex](https://openalex.org/). Qwen is limited to intent understanding and dynamic query planning; it does not establish research gaps. The persistent budget gate passed isolated local Upstash acceptance, and GitHub Actions on Ubuntu/Python 3.11 passed for the deployed code. Live public Qwen remains off pending safe recovery for unknown requests that retain concurrency slots and a separate cloud security review.

## Evaluation snapshot

On one frozen Chinese Golden Case, V0 branch-macro P@5 was **0.0500** (1 relevant result across 4 branch-level Top-5 lists, or 1/20) and nDCG@5 was **0.1077**; optimized rules V1 scored **0.8000** (12/15 across 3 branches) and **0.8210**. The branch sets differ, so this is not a controlled paired experiment or evidence of Qwen uplift. See [the evaluation case study](docs/EVALUATION_CASE_STUDY.md).

The [v2 evidence audit](docs/GOLDEN_CASE_V2_EVIDENCE_AUDIT.md) documents why the human-curated cards have different evidence coverage. The v2 demonstration does not change the frozen labels or V0/V1 scores.

## Screenshots

The three editable Streamlit pages have genuine browser viewport captures: [Intent Studio](docs/prototypes/01_AI_Intent_Studio.png), [Path Explorer](docs/prototypes/02_Research_Path_Explorer.png), and [Evidence & Next Steps](docs/prototypes/03_Evidence_Next_Steps.png). Each image is 1440×900 pixels and shows a naturally sized page viewport, not a smaller image padded onto a larger canvas. Page 3 shows the path 1 → Card A Golden Case v2 state; the evidence card continues below the viewport and can be scrolled in the live app. See [design spec](docs/prototypes/DESIGN_SPEC.md) for capture and snapshot provenance.

## LLM vs Rules：增量价值实验

Rules V1 already plans structured searches for known terms. This exploratory paired evaluation asks whether Qwen adds value on ambiguous, relational and long-tail requests. A uses Rules V1 and B uses Qwen V2; both share the same workflow, OpenAlex retrieval and post-processing.

| Machine-assisted provisional metric | Rules V1 | Qwen V2 |
|---|---:|---:|
| Precision@5 | 0.636 | **0.836** |
| nDCG@5 | 0.717 | **0.905** |

The frozen synthetic set contains 16 requests; **11/16** formed a complete live Top 5 pair. Qwen's source/target direction field was preserved in **0/8** applicable parsed intents, and its median end-to-end latency was **19.8 s** versus **1.6 s** for Rules. This supports a **Rules-first + Selective LLM** product direction: keep rules as the fast default and evaluate optional Qwen for complex requests, with relation validation and user confirmation.

These are machine-assisted provisional relevance labels, not completed human adjudication. S4 long-tail had no complete pair, and the implemented path selector chose the first relationship-cue match rather than the preregistered highest semantic match. See the [full report and audit](evaluation/llm_vs_rules_v1/RESULTS.md); the chart below uses the independently recalculated aggregate values.

![Rules V1 and Qwen V2 provisional paired evaluation](evaluation/llm_vs_rules_v1/metrics_chart.svg)

## Run locally

Use Python 3.11 (the current development version):

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

Set `OPENALEX_API_KEY` in the ignored local `.env` or `.streamlit/secrets.toml` for live OpenAlex retrieval. Qwen uses `DASHSCOPE_API_KEY`, but the existing development ledger is already exhausted. No Qwen call is needed to view the historical snapshot or use rule planning. Run tests with:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Scope and limitations

- OpenAlex results can be noisy. A retrieved paper is not automatically relevant or evidence-eligible.
- Abstract-only evidence is not full-text verification; every supported statement needs a source excerpt.
- Small search samples cannot prove a topic is unexplored or that a research gap exists.
- Public Evaluation displays frozen history and server-side save actions are disabled. On 2026-10-15 the deployed view still showed outdated targeted-review wording and editable-looking controls; a local UI patch removes those controls and corrects the copy, but needs a separately authorized push to become public.
- No production user study, usage-growth result, or live public Qwen call has been completed. Isolated live Upstash budget-gate checks passed locally; they are not a cloud Qwen safety test.
- Public URL: [https://research-compass-ai.streamlit.app/](https://research-compass-ai.streamlit.app/) (rules and historical snapshot; live public Qwen disabled).

## Product and release docs

- [PRD v1](docs/PRD_v1.md)
- [Evaluation case study](docs/EVALUATION_CASE_STUDY.md)
- [Release checklist and Cloud setup](docs/RELEASE_CHECKLIST.md)
- [Resume project summary](docs/RESUME_PROJECT.md)
- [3-minute demo script](docs/DEMO_SCRIPT.md)
- [Interview Q&A](docs/INTERVIEW_QA.md)
- [Delivery status](docs/DELIVERY_STATUS.md)
- [Portfolio overview](docs/PORTFOLIO_OVERVIEW.md)
- [Final delivery checklist](docs/FINAL_DELIVERY.md)
