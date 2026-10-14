# Research Compass — PRD v1.0

## Product goal

Help an early-stage researcher move from a vague interest to an evidence-aware, actionable next research step. The product guides exploration; it does not choose a research direction or claim that it has established a research gap.

## JTBD

When I have a broad topic but do not know the right academic terms or questions, help me clarify my intent, compare useful search paths, inspect relevant literature, and leave with a research plan I can continue validating.

## MVP experience

1. **AI Intent Studio** — accept a natural-language interest; optionally clarify one key ambiguity; preview editable domain, methods, goal and constraints; clearly label Qwen, rule fallback or historical snapshot.
2. **Research Path Explorer** — show two or three distinct paths and English academic queries. Search OpenAlex only after a path is selected. Display real title, abstract, year, source link, OpenAlex ID and relevance explanation. Cache completed path searches in the session.
3. **Evidence & Next Steps** — separate Evidence Landscape, Candidate Research Questions and Next Search. Keep paper relevance, eligibility for evidence generation, and claim-level support as distinct decisions. Cite abstract excerpts; label questions as hypotheses to verify; provide a copyable Research Plan Summary.

## Success measures

**Primary product outcome — Actionable Research Plan Completion:** among evaluation participants who start the workflow, the proportion who complete a plan containing a confirmed research objective, a selected path, at least one inspected source, and a concrete next search/action. Report numerator, denominator, task protocol and sample size. No representative user study has been completed yet; this is a proposed measure, not a measured result.

**AI/search quality:** intent preservation, human-rated Precision@5 and nDCG@5, direction coverage, irrelevant evidence rate, evidence-gate precision/recall, and claim support rate. Scores require human judgments and must state query set, branch set, thresholds, missing-label treatment and sample size.

**Operational cost and reliability:** Qwen token usage, estimated token cost, latency, failure rate, OpenAlex success/failure, and public budget reservations. Report estimates separately from provider invoices. The app-side budget gate is not an account-level billing guarantee.

## Scope and boundaries

- OpenAlex/PyAlex is the retrieval layer; this project adds an exploratory workflow around it.
- Abstract-only evidence is explicitly not full-text verification.
- A small retrieved sample cannot establish that a research direction is unstudied.
- No multi-agent system, PDF full-text indexing, vector database, account system, or long-term memory in v1.
- Evaluation is read-only in public deployment; editable judgments remain a private/local research asset.

## Failure handling

- Missing or failed Qwen: label rule-based fallback; never label it as AI output.
- Missing/failed persistent Redis budget gate in a public deployment: fail closed and use rules.
- Duplicate request, visitor limit, concurrency limit, open breaker or exhausted budget: do not call Qwen.
- OpenAlex outage: visibly label demo snapshot/fallback; never mix demo papers with live results.
- Too few eligible sources: state that evidence is insufficient; do not fabricate a landscape, limitation or research question.
- Unknown Qwen timeout outcome: retain the reservation and concurrency slot conservatively.

## Roadmap

- v1: three-page exploratory search flow, source-linked abstract evidence, editable intent, path selection and frozen evaluation case.
- Next: adjudicate the remaining NLP label, broaden the human-labeled case set, validate Cloud budget controls against real Upstash, and test actionable-plan completion with researchers.
- Later: improve multilingual intent/query alignment and claim-level evidence validation based on measured failures; only then consider broader corpora or full-text integrations.
