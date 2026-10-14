# Release Checklist — Research Compass

## Current state

- [x] Three-page Streamlit workflow and real OpenAlex retrieval path exist.
- [x] Golden Case snapshot, human labels, correction history and evaluation freeze are retained.
- [x] Public Qwen is default-off; public evaluation write operations have code-level guards.
- [x] App-side budget gate, simulation tests, and isolated real Upstash Lua EVAL/persistence/concurrency/failure acceptance completed locally.
- [ ] Abandoned concurrency-slot recovery is implemented and verified; unknown outcomes currently retain both the spend reservation and active slot indefinitely.
- [ ] Exact staged commit, source data and Git history have final owner review; historical scan found no credential pattern, but gitleaks was unavailable.
- [ ] GitHub commit reviewed and pushed by the owner.
- [ ] Streamlit Community Cloud deployment tested and public URL recorded.
- [ ] End-to-end browser test on deployed app completed.
- [ ] Public Qwen remains disabled until every cloud security check passes.

## Budget and Qwen gate

The service gate reserves ¥0.05 before a request against a persistent ¥5 counter. Model is limited to `qwen3.8-flash`, payload to 32,768 UTF-8 bytes, output to 1,800 tokens, request timeout to 25 seconds, visitor quota to 2/day, and global concurrency to 2. It uses one atomic Upstash Lua script; unknown outcome does not release the reservation or active slot. The reservation must not be refunded, but active-slot recovery is not implemented yet and can leave capacity blocked until manual intervention. Three definitive provider errors open a 15-minute breaker. No automatic model retry is configured.

This is an app-enforced reservation limit based on published token rates; it is not a provider-level billing cap and does not prove the external invoice cannot contain other charges. Never describe it as a strict ¥5 invoice ceiling.

## Private local configuration for real Redis verification

Create ignored `.streamlit/secrets.toml` from `.streamlit/secrets.toml.example`. For Streamlit Cloud, enter the same keys in the private Secrets panel. Fill only locally during preflight:

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `PUBLIC_BUDGET_HMAC_KEY` (random secret, at least 32 bytes)
- `PUBLIC_DEPLOYMENT = true` for read-only public-mode behavior
- Keep `PUBLIC_QWEN_ENABLED = false` and `PUBLIC_QWEN_SECURITY_REVIEW_PASSED = false`
- `OPENALEX_API_KEY` and (only for a separately approved Qwen deployment) `DASHSCOPE_API_KEY`, `DASHSCOPE_BASE_URL`, and `DASHSCOPE_MODEL`

Do not paste secrets into chat, Trace, screenshots, issue trackers, or Git. Once credentials exist, test the real atomic EVAL and durability with simulated reservations only; do not call Qwen for load tests.

## GitHub review and Streamlit Cloud steps

1. The current candidate has 111 explicitly staged paths (runtime, CI/config, docs/prototypes, tests and evaluation evidence); the exact list is recorded in `GIT_SUBMISSION_AUDIT.md`. `.vscode/tasks.json` is excluded as a local editor task. Review the staged name list and diff before commit.
2. `.env`, `.streamlit/secrets.toml`, and the local Qwen ledger are ignored and absent from the index; staged-content pattern scans found no key-shaped values, emails or local absolute paths. The current local Git checkout contains only one commit, so remote/full repository history still needs owner review before publishing.
3. Run `pytest -q`; review screenshots and evaluation files for privacy and accurate snapshot labels. The existing screenshots are browser renders captured at a 932×654 CSS viewport on 1440×900 canvases; they are not full desktop-layout validation.
4. Owner selects the existing repository and `app.py` in Streamlit Community Cloud, chooses Python 3.11 in Advanced settings, and privately enters Secrets.
5. Initial Cloud Secrets keep `PUBLIC_QWEN_ENABLED = false` and `PUBLIC_QWEN_SECURITY_REVIEW_PASSED = false`.
6. Confirm read-only Evaluation, OpenAlex behavior, missing-Redis fail-closed behavior, and no credential leakage in logs. Exact `PUBLIC_DEPLOYMENT=true` tests currently pass locally.
7. The isolated Upstash acceptance passed locally, but the active-slot recovery gap is still a blocker. Do not approve the security-pass switch or enable paid Qwen until stale-slot recovery is implemented and tested without early release.
8. Record the actual public URL only after successful deployment and browser verification.

Official references: [Qwen model pricing](https://help.aliyun.com/zh/model-studio/model-pricing), [Upstash Redis EVAL](https://upstash.com/docs/redis/sdks/ts/commands/scripts/eval), [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app), [Streamlit secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).
