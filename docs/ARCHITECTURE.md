# Architecture

## Two paths

```
COMPILE (slow, LLM-assisted)            ENFORCE (fast, deterministic, no LLM, <100ms)

grant PDF                                expense + ruleset + budget state
   │                                                │
   ▼                                                ▼
compiler/  ──proposes rules──▶  citation      enforce/  ──▶  verdict + clause trace
   │                            verifier                    (ALLOWED / BLOCKED / NEEDS_REVIEW)
   ▼                               │
typed rule IR (contracts/) ◀───────┘ unverifiable rules rejected
```

- Agents propose, deterministic code disposes.
- Every rule carries a verbatim clause quote, page, and char offsets, checked against the source PDF.
- Money is integer cents everywhere.

## Components

| Dir | Purpose | Owner |
|---|---|---|
| `contracts/` | Pydantic v2 schemas + exported JSON Schema | all 3 |
| `shared/` | LLM wrapper (`llm.py`), cache, logging, config | A |
| `compiler/` | PDF -> rule IR | A |
| `enforce/` | Rule evaluator | B |
| `web/` | Next.js UI | C |
| `fixtures/` | Grant PDFs, gold rulesets, labeled expenses | |
| `evals/` | Extraction + enforcement evals | |

## Judging notes

_TBD._
