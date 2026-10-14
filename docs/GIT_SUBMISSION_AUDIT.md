# Git Submission Audit — 2026-10-15

## Scope

The original review found 111 pending paths. This candidate stages 110 of them; `.vscode/tasks.json` is excluded as a machine-local editor task. This audit file is the 111th staged path. The exact paths below are the candidate set; review with `git diff --cached --name-only` before commit.

## Classification

- 20 runtime paths: `app.py`, `pages/`, `research_compass/`.
- 7 CI/config/dependency paths: workflow, requirements, `.gitignore`, `.env.example`, Streamlit config and Secrets template.
- 13 docs/prototype paths: README, product/release/portfolio docs, three browser screenshots and design spec.
- 11 test paths: unit tests plus isolated Upstash/TLS acceptance scripts.
- 60 evaluation paths: frozen traces, labels, correction events, snapshots, reports, run scripts, security evidence and freeze bundle.

## Security and exclusions

- Candidate scan found no API-key/token-shaped values, email-like data or local absolute paths in the staged text/bundle. The screenshots were visually reviewed for secrets.
- `.env`, `.streamlit/secrets.toml` and `evaluation/runs/v3_20261014/qwen_ledger.json` are ignored and absent from the Git index.
- `.vscode/tasks.json` remains untracked and excluded because it is a local editor launch task.
- The remote `origin` was checked read-only on 2026-10-15: its only advertised branch is `main` at `41f33e3613a3f4b684ce1be5d6f5071e36a74759`, exactly matching local `HEAD`; no tags were advertised. The checkout is not shallow, and this branch has one commit containing only `README.md`. A normal `git push origin main` after committing would be a fast-forward if the remote does not change in the meantime. No dedicated gitleaks binary was available.
- The staged 111 paths were also compared against seven locally configured credential/endpoint values without printing them. Only placeholder values in `.streamlit/secrets.toml.example` matched; no configured live credential matched staged content. Recheck the remote tip immediately before any push.
- Frozen `original_trace.json`, V1 `human_labels.csv` and `final_adjudication.csv` match their freeze-manifest hashes.

## Verification and release status

- Local pytest: 45 passed; `PUBLIC_DEPLOYMENT=true` Evaluation/write-guard subset: 5 passed; Python compilation passed.
- GitHub Actions targets Ubuntu/Python 3.11 but has not run because no push occurred.
- Real Upstash acceptance is recorded in `evaluation/security_acceptance/m3_release_acceptance_20261015.md`; no Qwen call or repeated live Redis test was made in this release review.
- Unknown provider outcomes currently preserve spend reservation and active concurrency slot without expiry/recovery. Public Qwen remains disabled until safe slot recovery is implemented and tested.
- Prototype PNGs are genuine historical browser renders at 932×654 CSS pixels placed on 1440×900 canvases; full desktop layout is not validated.
- No public deployment or URL exists. No commit or push was made.

## Exact candidate paths

- `.env.example`
- `.github/workflows/tests.yml`
- `.gitignore`
- `.streamlit/config.toml`
- `.streamlit/secrets.toml.example`
- `app.py`
- `docs/DELIVERY_STATUS.md`
- `docs/DEMO_SCRIPT.md`
- `docs/EVALUATION_CASE_STUDY.md`
- `docs/GIT_SUBMISSION_AUDIT.md`
- `docs/INTERVIEW_QA.md`
- `docs/PRD_v1.md`
- `docs/prototypes/01_AI_Intent_Studio.png`
- `docs/prototypes/02_Research_Path_Explorer.png`
- `docs/prototypes/03_Evidence_Next_Steps.png`
- `docs/prototypes/DESIGN_SPEC.md`
- `docs/RELEASE_CHECKLIST.md`
- `docs/RESUME_PROJECT.md`
- `evaluation/analyze_human_review.py`
- `evaluation/build_targeted_report.py`
- `evaluation/cases/badcase_001/BAD_CASE.md`
- `evaluation/cases/badcase_001/expected_intent.json`
- `evaluation/cases/badcase_001/original_trace.json`
- `evaluation/cases/v3_paired_cases.json`
- `evaluation/checkpoints/m0_20261014.md`
- `evaluation/checkpoints/m1_20261014.md`
- `evaluation/diagnose_qwen_network.py`
- `evaluation/freeze/final_20261014/adjudication.json`
- `evaluation/freeze/final_20261014/delivery_checklist.md`
- `evaluation/freeze/final_20261014/final_adjudication.csv`
- `evaluation/freeze/final_20261014/freeze_manifest.json`
- `evaluation/freeze/final_20261014/gate_metrics.json`
- `evaluation/freeze/final_20261014/source_and_evaluation.zip`
- `evaluation/freeze_delivery.py`
- `evaluation/reports/human_review_v0_v1_20261014/labels_snapshot.csv`
- `evaluation/reports/human_review_v0_v1_20261014/metrics.json`
- `evaluation/reports/human_review_v0_v1_20261014/report.md`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T083729473965Z_8aef5fb0eed5476b9b0c4a2eaf3f9945.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T083926387070Z_76b27c72fa94486bbabc437e8fed6613.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T084048957811Z_661e63dd4e7c41bbb739bee17c7bd8ca.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T084057555666Z_b0927dd83dd649799b00ce9b55719c29.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T084059630852Z_5730ce4aff964f899890d3b4184c3f56.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T084101609611Z_ca619349d46846cfb487fb550dad45e9.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T084103854588Z_f407523c08254832a32b12b3ca512f5a.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T084133526070Z_5428d7112604423baeb87ab1757c2bdd.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T084156676320Z_63275df017ae40368ba7a144ded390c2.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T084206915426Z_afb816d430df4a0ba12146ee3a5a329d.json`
- `evaluation/reports/targeted_review_v1_20261014/changes/20261014T084222005981Z_bd35d243e31f45c3a867ed132dbadd73.json`
- `evaluation/reports/targeted_review_v1_20261014/human_labels_reviewed.csv`
- `evaluation/reports/targeted_review_v1_20261014/metrics.json`
- `evaluation/reports/targeted_review_v1_20261014/report.md`
- `evaluation/run_p0_live.py`
- `evaluation/run_p0_snapshot.py`
- `evaluation/run_v3_intent_comparison.py`
- `evaluation/run_v3_live_openalex.py`
- `evaluation/runs/p0_20261014/human_review.csv`
- `evaluation/runs/p0_20261014/live_openalex.json`
- `evaluation/runs/p0_20261014/llm_strategy.md`
- `evaluation/runs/p0_20261014/metrics.json`
- `evaluation/runs/p0_20261014/README.md`
- `evaluation/runs/p0_20261014/snapshot_replay.json`
- `evaluation/runs/v3_20261014/golden_qwen_live_20261014.json`
- `evaluation/runs/v3_20261014/human_labels.csv`
- `evaluation/runs/v3_20261014/live_openalex_golden.json`
- `evaluation/runs/v3_20261014/live_openalex_golden_initial.json`
- `evaluation/runs/v3_20261014/live_openalex_golden_untimed.json`
- `evaluation/runs/v3_20261014/live_openalex_human_review.csv`
- `evaluation/runs/v3_20261014/live_openalex_human_review_initial.csv`
- `evaluation/runs/v3_20261014/live_openalex_human_review_untimed.csv`
- `evaluation/runs/v3_20261014/planner_comparison.json`
- `evaluation/runs/v3_20261014/quality_cost_comparison.json`
- `evaluation/runs/v3_20261014/quality_cost_comparison.md`
- `evaluation/runs/v3_20261014/run_golden_once.py`
- `evaluation/security_acceptance/m3_release_acceptance_20261015.md`
- `evaluation/security_acceptance/upstash_live_0070fea67c8749f2b5bff5c7cddd05de.json`
- `evaluation/security_acceptance/upstash_live_3f56c7a901f34ccf8e56cf749c8c886c.json`
- `evaluation/security_acceptance/upstash_live_tls_blocked_20261015.json`
- `evaluation/write_v3_comparison_report.py`
- `pages/1_Home.py`
- `pages/1_Intent_Studio.py`
- `pages/2_Evaluation.py`
- `pages/2_Path_Explorer.py`
- `pages/3_Evidence_Next.py`
- `README.md`
- `requirements.txt`
- `requirements-dev.txt`
- `research_compass/__init__.py`
- `research_compass/evidence.py`
- `research_compass/exploration.py`
- `research_compass/human_eval.py`
- `research_compass/planning.py`
- `research_compass/prototype_snapshot.py`
- `research_compass/public_budget.py`
- `research_compass/qwen_planning.py`
- `research_compass/retrieval.py`
- `research_compass/targeted_report.py`
- `research_compass/targeted_review.py`
- `research_compass/targeted_review_ui.py`
- `research_compass/trace.py`
- `research_compass/ui_theme.py`
- `tests/test_day1.py`
- `tests/test_day2.py`
- `tests/test_evaluation_page.py`
- `tests/test_human_eval.py`
- `tests/test_m1_flow.py`
- `tests/test_page.py`
- `tests/test_public_budget.py`
- `tests/test_qwen_planning.py`
- `tests/test_targeted_review.py`
- `tests/upstash_live_acceptance.py`
- `tests/upstash_tls_diagnostic.py`
