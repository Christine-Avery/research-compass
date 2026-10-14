# M3 Release Security Acceptance — 2026-10-15

## Outcome

The local M3 Upstash budget gate passed its live acceptance against Upstash using an isolated test namespace. Public Qwen remained disabled throughout. This is not a cloud deployment approval: Linux CI was configured but not executed, and Qwen remains off.

## TLS diagnosis and repair

- Windows time synchronization is healthy (`time.windows.com`; leap indicator 0; last sync 2026-10-15 01:02:38 local time).
- Before the repair, Windows Schannel verified the endpoint, while Python 3.11.8 / OpenSSL 3.0.13's default CA path failed with verify code 10 (`certificate has expired`). A certifi-backed, strict Python request succeeded.
- Upstash REST EVAL and the unauthenticated diagnostic now share `build_upstash_opener()` in `research_compass/public_budget.py`. It loads certifi's CA bundle, requires certificates and hostname verification, rejects redirects, and continues using normal urllib proxy discovery. The app and diagnostic send HTTPS only.
- Post-fix unauthenticated HEAD through the exact application transport returned HTTP 401 in 179.9 ms. This is the expected unauthenticated response and proves TLS validation succeeded; no token or Redis command was sent by this check.
- The default Python trust path still reports the old error when tested independently. The failure is isolated from the application's repaired trust path. The exact expired certificate selected by that default verifier was not exposed by its exception, so no specific certificate is asserted as the proven cause.

## Live Upstash acceptance

Final report: `upstash_live_3f56c7a901f34ccf8e56cf749c8c886c.json`.

All Redis keys were confined to `rc-test:acceptance:3f56c7a901f34ccf8e56cf749c8c886c`. The formal `research_compass:public:v1` budget namespace was not touched.

| Check | Result |
|---|---|
| Unauthenticated strict TLS preflight | Pass; HTTP 401, no EVAL |
| Real Upstash EVAL | Pass (`PING` via EVAL) |
| Concurrent reservation cap | Pass; 2 admitted of 8, configured maximum 2 |
| Same-query race/idempotency | Pass; 1 admitted of 8 |
| Manager reconstruction and separate-process idempotency | Pass |
| Cross-process budget and concurrency visibility | Pass; two separate processes observed 100,000 micro-CNY reserved and two active slots; third reservation rejected |
| Isolated ¥5 / ¥0.05 boundary | Pass; 100 synthetic reservations reached exactly 5,000,000 micro-CNY; request 101 was rejected as `budget_exhausted` |
| Daily visitor quota | Pass; third distinct request rejected after two admissions |
| Unknown timeout after reservation | Pass; no provider call was made; reserved amount and active slot remained |
| Invalid Redis authentication | Pass; rejected and surfaced fail-closed |
| Redis script write/type error | Pass; generated only on a unique test key and surfaced fail-closed |
| Transport timeout and disconnect | Pass in deterministic injected transport-fault tests; these were not induced against the live Upstash service |
| Qwen/model calls | 0; both public Qwen switches were false |

The 100 reservations are synthetic Redis counter checks only. They are not Qwen usage or charges. The unique test keys are intentionally retained; the database was not cleared and no formal budget was reset.

## Code, tests, and budget isolation

- `requirements.txt` now explicitly includes `certifi>=2025.1.31,<2027`; the configured environment is Python 3.11.8 with certifi 2026.7.22.
- Full local pytest: **45 passed**.
- With `PUBLIC_DEPLOYMENT=true`, Evaluation and targeted-review tests: **5 passed**. Local write tests explicitly select non-public mode; public read-only tests continue to verify the write guard.
- Python compilation: **passed** for app, pages, package, and tests.
- `.github/workflows/tests.yml` targets Ubuntu and Python 3.11, but GitHub Actions/Linux CI was **not executed** in this acceptance.
- The public Redis counter uses the separate `research_compass:public:v1` namespace and has no expiry/reset operation; reservation increments are atomic. The local Qwen ledger remains separate at `evaluation/runs/v3_20261014/qwen_ledger.json`: 5 attempts / 5 records, estimated reserved CNY 0.0226572, local cap 5 calls and CNY 0.10. Neither ledger was reset or edited.
- `.streamlit/secrets.toml`, `.env`, and the local Qwen ledger are ignored and are not in the current Git index. Text-pattern checks found no key-shaped values in the working tree or the 40 available commits. The Qwen ledger path does exist in three historical revisions, but scans found no API-key, authorization, or token marker there. A dedicated `gitleaks` executable was unavailable, so this is not a certified secret scan.
- No Git files were staged, committed, pushed, or deployed.

## Remaining risks and release status

- M3's local persistent-budget and fail-closed checks passed. Public Qwen must remain disabled until cloud Secrets, Linux CI, and the final deployment security review are completed.
- Deterministic timeout/disconnect tests cover client fail-closed behavior; a real Upstash outage or network timeout was not induced.
- The Python default CA path still fails in this Windows environment, although the app's explicit certifi path passes. Keep certifi updated and retain the strict TLS regression test.
- Upstash's own service restart/failover was not forced. Persistence across fresh managers and separate application processes was verified against the same Redis database; the global budget key is not initialized/reset on application startup.
- No public URL was created or tested.

## Commit review checklist

Current Git state has no staged files; most project files are still untracked. Review and stage deliberately rather than using `git add .`.

M3 changes and evidence:

- `requirements.txt`
- `research_compass/public_budget.py`
- `tests/upstash_tls_diagnostic.py`
- `tests/upstash_live_acceptance.py`
- `tests/test_public_budget.py`
- `tests/test_evaluation_page.py`
- `tests/test_targeted_review.py`
- `evaluation/security_acceptance/upstash_live_3f56c7a901f34ccf8e56cf749c8c886c.json`
- `evaluation/security_acceptance/m3_release_acceptance_20261015.md`

Before a first project commit, separately review the existing untracked app, pages, `research_compass/`, docs, frozen evaluation artifacts, and screenshots. Exclude `.streamlit/secrets.toml`, `.env`, and `evaluation/runs/v3_20261014/qwen_ledger.json`. Do not rewrite repository history as part of this acceptance.
