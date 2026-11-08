import time
from collections.abc import Mapping, Sequence

from contracts.models import (
    BudgetState,
    EnforcementResult,
    Expense,
    RuleOutcome,
    Ruleset,
    RuleTrace,
)
from contracts.verdict import Verdict
from enforce.rules import evaluate_rule, is_rule_applicable


def evaluate_expense(
    expense: Expense,
    ruleset: Ruleset | Sequence[Ruleset],
    budget_state: BudgetState,
    budgets: Mapping[str, BudgetState] | None = None,
) -> EnforcementResult:
    """Evaluate an expense against one or more rulesets and current budget state.

    `budgets` optionally gives each ruleset its own budget, keyed by grant id
    (two grants can both have a "travel_domestic" line); rulesets without an
    entry use `budget_state`.

    Several rulesets (e.g. a grant and the company's own policy) are checked
    together; the strictest outcome wins, and each trace says which source
    decided. Only approved rules are enforced.

    Guarantees:
    - Pure deterministic evaluation (no LLM, no external I/O).
    - Sub-millisecond latency (<100ms contract requirement).
    - Integer cents precision throughout.
    - Ambiguity escalates to NEEDS_REVIEW; failures block to BLOCKED.
    """
    start_ns = time.perf_counter_ns()
    rulesets = [ruleset] if isinstance(ruleset, Ruleset) else list(ruleset)

    traces: list[RuleTrace] = []
    has_fail = False
    has_escalate = False

    for rs in rulesets:
        rs_budget = (budgets or {}).get(rs.grant_id, budget_state)
        for rule in rs.rules:
            if rule.status != "approved" or not is_rule_applicable(rule, expense):
                continue

            trace = evaluate_rule(rule, expense, rs_budget)
            traces.append(trace)

            if trace.outcome == RuleOutcome.FAIL:
                has_fail = True
            elif trace.outcome == RuleOutcome.ESCALATE:
                has_escalate = True

    if has_fail:
        verdict = Verdict.BLOCKED
    elif has_escalate:
        verdict = Verdict.NEEDS_REVIEW
    else:
        verdict = Verdict.ALLOWED

    elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0

    return EnforcementResult(
        verdict=verdict,
        traces=traces,
        latency_ms=round(elapsed_ms, 3),
    )
