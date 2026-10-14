# Delivery Status

## Implemented

- Three Streamlit pages for intent, search paths and evidence/next steps.
- OpenAlex/PyAlex retrieval and cached path results; source IDs, links and abstracts are shown.
- Snapshot disclosures and rule fallback states.
- Read-only public Evaluation guards.
- Public Qwen budget gate with persistent Upstash REST EVAL interface, default-off switches, simulation tests and an isolated live Upstash acceptance report.
- Frozen evaluation docs, prototype screenshot integrity note, PRD, demo script, resume and interview Q&A.

## Tested locally

- Simulated atomic reservation/concurrency, duplicate request, budget exhaustion, visitor quota, breaker, no-refund behavior, unknown timeout slot retention, process recreation and default-off state.
- M3 live Upstash acceptance: isolated real EVAL, persistence across managers/processes, concurrency, idempotency, budget boundary and fail-closed behavior passed; no Qwen API request was made.
- Local release-candidate pytest: 45 passed; Python compile check passed.
- `PUBLIC_DEPLOYMENT=true` Evaluation and targeted-review guard tests: 5 passed; no cloud browser verification has run.

## Not completed / release blockers

- Unknown Qwen outcomes retain the spend reservation and active slot with no expiry/recovery path. This preserves the budget but can permanently exhaust concurrency capacity; public Qwen remains blocked until safe abandoned-slot recovery is implemented and verified.
- Real Upstash acceptance used a separate isolated test namespace. It verified shared state across fresh managers/processes, not a forced Upstash service restart/failover.
- Public Qwen must remain off. No GitHub Actions run, Cloud deployment or public URL exists yet.
- Git candidate audit completed: 111 paths explicitly staged, `.vscode/tasks.json` excluded, staged-content secret/PII/path-pattern checks clear. The local checkout contains one commit, so remote history still needs owner review. No commit or push was performed.
- M2 screenshots are genuine browser renders at a 932×654 viewport on 1440×900 canvases; full desktop layout remains visually unverified.
- NLP label conflict remains unresolved and unchanged.

## Owner actions

1. Implement and test stale concurrency-slot recovery so the spend reservation remains charged while abandoned capacity becomes available only after a conservative request deadline.
2. Review the exact staged file list and Git history scan; approve the GitHub commit/push when ready.
3. After push, confirm Ubuntu/Python 3.11 GitHub Actions passes, then configure Streamlit Community Cloud and its private Secrets panel with both Qwen switches false.
4. Run cloud read-only, retrieval, rate-limit, fail-closed and responsive browser checks. Keep public Qwen off until its own security review is approved.
