# shared/llm.py LLM client

Branch: `a/llm-client` · Owner: A

## Scope
- [ ] Single entry point for every LLM call
- [ ] Disk cache keyed by prompt hash; structured logging; retry cap
- [ ] Temperature 0 for extraction/classification
- [ ] Config/env loading (shared/config.py, .env.example)

## Done when
Compiler can call the LLM through shared/llm.py with cached, logged, reproducible responses.
