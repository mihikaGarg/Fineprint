# Deterministic rule evaluator

Branch: `b/evaluator` · Owner: B

## Scope
- [ ] Tests first, table-driven per rule kind
- [ ] evaluate(expense, ruleset, budget_state) -> Decision, no LLM calls
- [ ] Unknown category or unmappable budget line escalates
- [ ] Hypothesis property tests: integer cents, verdict follows trace

## Done when
All rule kinds evaluated correctly; p95 under 100ms.
