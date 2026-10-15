# Research Compass — Final Delivery

Last checked: 2026-10-15. Public app: https://research-compass-ai.streamlit.app/ · Source: https://github.com/Christine-Avery/research-compass.

| Deliverable | Path | Complete | Practical acceptance | Limits | Publish? |
|---|---|---:|---|---|---|
| Product MVP | Public Streamlit URL | Yes | Public pages loaded; rule default and OpenAlex workflow are deployed | Public Qwen disabled | Already public |
| Golden Case v2 | `research_compass/golden_v2.py`, `research_compass/golden_v2_ui.py`; Page 2 and Page 3 | Yes | Public browser: path 1→A, 2→C, 3→B; only selected card; no stale card on switch | Human-curated saved evidence, not live Qwen | Already public |
| PRD | `docs/PRD_v1.md` | Yes | Scope, three pages, metric, failure handling, current boundary | User outcome not yet studied | Local final changes need push for GitHub copy |
| Evaluation | `docs/EVALUATION_CASE_STUDY.md` | Yes | Frozen metrics and limits stated; labels and traces untouched | One query; pending NLP decision | Local copy fix needs push |
| Prototype screenshots | `docs/prototypes/01_AI_Intent_Studio.png`, `02_Research_Path_Explorer.png`, `03_Evidence_Next_Steps.png` | Yes | Genuine 1440×900 browser viewport captures inspected; Page 3 shows path 1→Card A | Card content continues below viewport and scrolls; captures are historical Golden Case data | Include in portfolio |
| Design specification | `docs/prototypes/DESIGN_SPEC.md` | Yes | Captured viewport and data provenance disclosed | Full desktop visual validation pending | Local final changes need push |
| README | `README.md` | Yes | Public URL, flow, architecture, metrics and limits present | Mentions deployed public Evaluation copy issue | Local final changes need push |
| Resume project | `docs/RESUME_PROJECT.md` | Yes | 100–150 Chinese character summary plus role-tailored bullets | No user growth/efficiency claims | Local final changes need push |
| Portfolio overview | `docs/PORTFOLIO_OVERVIEW.md` | Yes | Pain, flow, decisions, case, metrics, risks, roadmap and links | No user study or commercial outcome | Local final changes need push |
| Demo script | `docs/DEMO_SCRIPT.md` | Yes | Three-minute and one-minute versions; path1→A primary | Snapshot must be described as historical | Local final changes need push |
| Interview Q&A | `docs/INTERVIEW_QA.md` | Yes | 13 grounded answers covering product, quality, safety and AI collaboration | Qwen live metrics unavailable | Local final changes need push |
| Delivery status | `docs/DELIVERY_STATUS.md` | Yes | Passed, blocked and owner actions separated | Public Evaluation copy fix not deployed | Local final changes need push |
| Public Evaluation UX patch | `pages/2_Evaluation.py`; `tests/test_evaluation_page.py` | Yes, local | Focused test 2 passed; full pytest 57 passed | Cloud still has old wording/controls until separately authorized push and deploy | Needs review/push |
| Frozen evaluation data | `evaluation/runs/v3_20261014/human_labels.csv` and freeze directory | Preserved | Worktree SHA-256 = Git HEAD blob SHA-256 = freeze hash `00168b25…70b0aa` | One NLP label remains disputed | Never modify |
| CI | GitHub Actions run `38695386201` | Yes | Ubuntu/Python 3.11 success on deployed commit `cb68c78ac7ac244179b642c8542f6e53b2d435cd` | Does not cover this later local-only patch | New CI requires push |
| Public Qwen budget gate | `public_budget.py`; prior isolated acceptance report | Qwen disabled | Prior real Upstash isolated acceptance passed; no live model calls in this final round | Unknown outcome can retain concurrency slots indefinitely; not safe to enable | Do not enable |

## Release decision

This project is ready to use as an AI PM portfolio demo with explicit limits. The genuine desktop viewport captures and their provenance are included in the portfolio files. Do not enable public Qwen until concurrency-slot recovery and a fresh cloud security review pass. Any outstanding documentation or Evaluation copy patch still requires its own reviewed commit and ordinary-push authorization before it becomes public.
