# Fineprint plan

Goal: a live demo where a real grant PDF compiles into cited rules, and expenses get ALLOWED / BLOCKED / NEEDS_REVIEW verdicts in under 100ms, each linked to the exact clause in the PDF.

Workstream plans: [compiler.md](compiler.md) (A), [enforce.md](enforce.md) (B), [web.md](web.md) (C).

## Milestones

Each milestone ends with `make check` green on main and something you can show.

### M0: Contracts frozen (done when all three agree)
- [x] Draft schemas in `contracts/` (SCHEMA_VERSION 0.2.0)
- [ ] Team agrees on rule kinds, expense categories, and who assigns `Expense.category`
- [ ] One hand-written gold ruleset in `fixtures/rulesets/` that validates

### M1: Walking skeleton
Fake data end to end, no LLM.
- [ ] A: `compiler` CLI loads a PDF and emits the hand-written gold ruleset
- [ ] B: `enforce.evaluate(expense, ruleset, budget_state) -> Decision` handles all 5 rule kinds
- [ ] B: FastAPI `POST /evaluate` and `GET /rulesets/{id}`
- [ ] C: Page lists expenses with verdict badges from `/evaluate`

### M2: Real compile
- [ ] A: PDF text extraction with per-page text and stable char offsets
- [ ] A: Citation verifier rejects any rule whose quote doesn't match the PDF span
- [ ] A: LLM extraction via `shared/llm.py` produces a verified ruleset for 1 real grant
- [ ] C: Clause trace view highlights the cited span in the PDF

### M3: Evals and hardening
- [ ] 2–3 real grant PDFs in `fixtures/grants/` with gold rulesets
- [ ] 30+ labeled expenses in `fixtures/expenses/` covering every rule kind and edge case
- [ ] `evals/extraction`: precision/recall of compiled rules vs gold
- [ ] `evals/enforcement`: verdict accuracy (target 100%, since it's deterministic) and p95 latency
- [ ] Hypothesis property tests for enforce (money never negative, verdict follows trace)

### M4: Demo polish
- [ ] Demo script rehearsed (below)
- [ ] Judging notes in `docs/ARCHITECTURE.md`
- [ ] Cached LLM responses checked in so the demo works offline

## Demo script (3 minutes)
1. Upload a real grant agreement. Show the compiled rules, each with its quoted clause and page.
2. Run a batch of expenses. Most are ALLOWED; show the latency number.
3. Click a BLOCKED expense (e.g. alcohol). The trace jumps to the clause in the PDF.
4. Show a NEEDS_REVIEW expense (e.g. equipment over threshold, no prior approval). The system escalates instead of guessing.
5. Show that the enforce path makes zero LLM calls, and that each rule's citation is checked against the PDF.

## Open questions
- Which real grants do we use? (Public NSF/NIH/foundation agreements are easiest.)
- Who assigns `Expense.category`: Ramp merchant codes, a classifier step, or manual?
- Do we need indirect-cost-rate caps or Fly America rules for the demo grants?
- Persistence: SQLite via SQLAlchemy, or in-memory for the demo?
