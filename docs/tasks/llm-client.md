# shared/llm.py LLM client

Branch: `a/llm-client` · Owner: A

## Scope
- [x] Single entry point for every LLM call (`shared.llm.complete_json`)
- [x] Disk cache keyed by prompt hash; structured logging (no prompt text or keys); retry cap
- [ ] ~~Temperature 0~~ not supported by current models; cache gives reproducibility instead
- [x] Config/env loading (`.env.example`, `FINEPRINT_LLM_MODEL`, `FINEPRINT_PROPOSER`)
- [x] LLM proposer (`compiler/llm_propose.py`) with code-derived params and citation verification
- [ ] First real run on a public grant PDF (needs ANTHROPIC_API_KEY)

## Done when
Compiler can call the LLM through shared/llm.py with cached, logged, reproducible responses.
