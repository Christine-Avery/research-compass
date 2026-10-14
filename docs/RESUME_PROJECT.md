# Resume Project — Research Compass

## AI Search / AI Product Manager project

**Research Compass — AI Exploratory Search for Research** | Product strategy, prototype and evaluation | 2026

- Framed an unmet search need for novice researchers: translating vague interests into intent, candidate search paths, source inspection and a verifiable next step.
- Defined a three-page workflow: editable intent clarification, user-selected OpenAlex search paths, and abstract-grounded evidence/next steps.
- Built a Streamlit/PyAlex prototype around OpenAlex rather than implementing a new scholarly corpus; separated retrieved, relevant, evidence-eligible and claim-supported states.
- Preserved a Golden Case and 35 branch-level human judgments. In one case, rule V1 measured P@5 0.80 and nDCG@5 0.8111 versus V0 0.05 and 0.1077; variants had different branch sets, so results are directional and not statistically generalizable.
- Designed a fail-closed public Qwen budget gate using atomic Upstash Redis reservation. An isolated real-service acceptance passed locally; stale active-slot recovery and cloud validation remain release blockers, so public Qwen stays disabled.

## Interview framing

Emphasize product discovery framing, evidence-aware UX, explicit uncertainty, human evaluation and cost-aware rollout. State clearly that the work is a prototype with a single Golden Case, not a deployed product or measured user outcome. Do not claim production security, a hard invoice cap, Qwen quality lift, or user growth.
