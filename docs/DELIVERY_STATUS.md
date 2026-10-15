# Research Compass — Delivery Status

Updated 2026-10-15 after public Golden Case v2 browser review.

## Delivered and checked

- Public Streamlit app: https://research-compass-ai.streamlit.app/; GitHub: https://github.com/Christine-Avery/research-compass.
- Three-page Streamlit MVP: rule-based intent planning, selectable search paths, OpenAlex retrieval, abstract evidence, next-search editing and plan summary.
- Human-curated Golden Case v2 is deployed. Public browser confirmed path 1 → A, path 2 → C and path 3 → B; only the selected card appeared. The cards use saved historical records and identify further reading/cross-path sources.
- Public home defaults to Local Rules V1 and states live AI is not open. No Qwen request was made in this delivery.
- GitHub Actions run 38695386201 passed on Ubuntu/Python 3.11 for commit cb68c78ac7ac244179b642c8542f6e53b2d435cd.
- Existing local suite previously passed 57 tests; targeted evaluation public-write-guard tests are included in the current local patch and must be rerun before any commit.
- Real Upstash isolated acceptance and 45-test release candidate results are retained from the prior M3 handoff; this final round did not repeat live Redis or paid tests.

## Current limits

- Public live Qwen is not safe to enable: unknown outcomes can retain active concurrency slots indefinitely. Both public switches must remain false until a conservative, tested recovery design and cloud review pass.
- On 2026-10-15 the public Evaluation route showed frozen history and disabled save actions, but also outdated copy about targeted review and controls that appeared editable. A local-only UI patch hides edit controls and corrects copy; it has not been pushed or deployed. No labels were changed.
- Prototype PNGs are 1440×900 image files but were captured from a 932×654 CSS viewport. They are real browser renders with unused blank canvas, not true full-desktop screenshots.
- V0/V1 quality figures cover one Chinese query with different branch sets; no generalization or Qwen lift is established. One NLP label dispute remains pending.
- Actionable Research Plan Completion has not been measured with participants. Public search behavior was checked, but this is not a reliability or usability study.

## Suggested next actions

1. Run local targeted and full pytest for the pending Evaluation copy/read-only patch.
2. Review the precise final diff; authorize an ordinary push if the public Evaluation copy fix is wanted online.
3. Capture new full-desktop screenshots using an actual 1440×900 browser viewport when such capture access is available; replace current files only with genuine viewport captures.
