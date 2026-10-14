# AI Search PM Interview Q&A

1. **What user problem did you choose?** Early researchers can have a topic but lack the vocabulary and structure to formulate a productive query. The product supports exploration from intent to a next search.
2. **How is this different from an AI paper search engine?** Search remains grounded in OpenAlex, while the product adds visible intent clarification, distinct paths, user choice and evidence-aware next steps.
3. **Why OpenAlex/PyAlex?** Reuse an existing scholarly index and client to focus MVP effort on the user workflow rather than building corpus infrastructure.
4. **How do you avoid hallucinated research gaps?** Separate abstract-supported limitations from AI-inferred opportunities, label questions as hypotheses, and state when the retrieved evidence is insufficient.
5. **What is the difference between relevance and evidence eligibility?** A paper may be relevant to a topic while its available abstract does not support a particular evidence-generation use. Claim-level support is a third distinct check.
6. **What did the evaluation show?** On one Golden Case, rule V1 P@5 was 0.80 / nDCG@5 0.8111 vs V0 0.05 / 0.1077. Branch sets differ, sample size is one query, and the result is preliminary.
7. **Did Qwen improve quality?** No such claim is supported. The frozen quality comparison is V0/V1 rules, not a controlled Qwen comparison.
8. **How do you control model cost?** A persistent Redis atomic reservation enforces the app-side ¥5 budget counter, per-visitor quota, concurrency cap and breaker. Isolated real Upstash acceptance passed locally; however, ambiguous timeouts can retain concurrency slots indefinitely, so cloud release and public Qwen remain blocked until recovery is safely implemented and tested. This is not a provider invoice cap.
9. **What is the primary product metric?** Actionable Research Plan Completion: the share of starters who finish with confirmed objective, selected path, inspected source and a concrete next action, measured in a defined task study. It has not yet been measured with participants.
10. **What would you do next?** Finish real Cloud budget verification, adjudicate the remaining NLP label without editing history, collect more diverse human-labeled tasks, and evaluate plan completion before scaling features.
