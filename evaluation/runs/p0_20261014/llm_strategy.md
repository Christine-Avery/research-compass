# LLM option for Research Compass P0 (proposal only)

No LLM provider is wired into this run. All P0 behavior currently uses deterministic local rules, and no API key was read or sent to an LLM.

## Recommendation and fallback

For a no-metered-cost experiment, use **Qwen3.5 9B Q4_K_M through local Ollama** if the development machine has enough memory; the published model download is about 6.6–7.6 GB. Use **Qwen3.5 4B Q4_K_M** (about 3.3–4.0 GB) on a tighter machine, with human review for more complex role/direction parsing. Ollama exposes a local chat endpoint and does not require a cloud API key. Model size is a download/storage requirement; local runtime speed depends on the machine.

If local quality is insufficient, the proposed hosted alternative is **GPT-5.4 mini**. Its current official API pricing is $0.75 / 1M input tokens and $4.50 / 1M output tokens. It is a paid option and is not enabled until the user explicitly approves its use. A lower-cost comparison option is GPT-5.4 nano; use only after checking its current official rates and quality for Chinese relation extraction.

## Minimal call plan

At most **two model calls per search session**, never one call per branch:

1. **Intent + planning**: parse domain, concepts, source/target roles, task, relation, explicit/inferred/unconfirmed conditions; generate 2–3 distinct branch queries. Target budget: 1,200–1,800 input and 500–800 output tokens.
2. **Evidence synthesis**: after deterministic retrieval and evidence gates, pass only evidence-eligible abstracts with IDs and ask for a concise landscape and candidate RQs. Require each claim to return evidence IDs and exact supporting spans; verify spans locally. Target budget: 4,000–7,000 input and 500–900 output tokens. If no evidence passes, do not call this step.

Estimated hosted usage per session: **5,200–8,800 input tokens and 1,000–1,700 output tokens**. At GPT-5.4 mini's listed standard rates this is approximately **$0.0084–$0.0143 per search session** (input and output billed separately), excluding retries and any future price change. A safety budget of **$0.02/session** covers small prompt/retry variance. This is a projection, not measured spend. Current run cost is **$0** because no LLM is called.

## Secrets and degradation

- Local Ollama: no API key; configure an optional local base URL/model name in untracked `.env` or Streamlit Secrets only if integration is approved.
- Hosted provider: store `OPENAI_API_KEY` in the process environment, local `.env`, or `.streamlit/secrets.toml`; keep those files git-ignored. Never print or serialize the key. Do not put keys in source, traces, screenshots, or browser-visible output.
- If LLM is unavailable, keep the current deterministic term normalization, conservative intent parser, editable user confirmation, and relevance/evidence gates. Mark the mode as `rules_fallback`; do not present rules as model output. Ask the user to clarify or leave fields unconfirmed instead of guessing.

Sources checked 2026-10-14: [OpenAI GPT-5.4 mini model and pricing](https://developers.openai.com/api/docs/models/gpt-5.4-mini), [Ollama Qwen3.5 model family](https://ollama.com/library/qwen3.5), [Qwen3.5 4B Q4_K_M details](https://registry.ollama.com/library/qwen3.5%3A4b-q4_K_M).
