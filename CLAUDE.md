# Fineprint
AI that compiles grant agreements into enforceable spend rules and checks expenses against them, with verified clause citations. Ramp x BBS hackathon. Tagline: "Every dollar, cleared by the clause."

## Non-negotiable architecture
- Two paths. COMPILE (slow, LLM-assisted): grant PDF -> typed rule IR. ENFORCE (fast, deterministic, NO LLM calls, target <100ms): expense + ruleset + budget state -> verdict + clause trace.
- Agents propose, deterministic code disposes. No LLM output may directly approve or block a payment.
- Every rule carries verbatim clause quote + page + char offsets, verified against the source PDF. Unverifiable rules are rejected.
- All money is integer cents. No floats for money. LLMs never do arithmetic.
- Verdicts: ALLOWED / BLOCKED / NEEDS_REVIEW. Ambiguity escalates; it is never guessed.
- Every LLM call goes through shared/llm.py (response cache by prompt hash, structured logging, retry caps, temperature 0 for extraction/classification).

## Layout and ownership
- /contracts   shared schemas (Pydantic v2 + exported JSON Schema). Changes need all 3 approvals; bump SCHEMA_VERSION.
- /shared      LLM client wrapper, cache, logging, config. Owner: A.
- /compiler    Owner: A
- /enforce     Owner: B
- /web         Owner: C
- /fixtures    real grant PDFs, gold rulesets, labeled expenses
- /evals       extraction + enforcement eval sets and runners
- /docs        ARCHITECTURE.md (design + judging notes)

## Conventions
- Python 3.12, uv, FastAPI, Pydantic v2, SQLAlchemy 2, pytest, hypothesis, ruff, pyright. Next.js + TypeScript + Tailwind in /web.
- Branches: a/<task>, b/<task>, c/<task>. Never push to main. Small PRs, squash merge.
- Never edit another owner's directory or /contracts without asking. Write tests first for evaluator and citation verifier.
- Run `make check` (ruff + pyright + pytest) before every commit.
- Record non-obvious decisions in docs/DECISIONS.md (one line each: date, decision, why).
