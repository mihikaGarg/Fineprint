import time

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
    ruleset: Ruleset,
    budget_state: BudgetState,
) -> EnforcementResult:
    """Evaluate an expense against a grant ruleset and current budget state.

    Guarantees:
    - Pure deterministic evaluation (no LLM, no external I/O).
    - Sub-millisecond latency (<100ms contract requirement).
    - Integer cents precision throughout.
    - Ambiguity escalates to NEEDS_REVIEW; failures block to BLOCKED.
    """
    start_ns = time.perf_counter_ns()

    traces: list[RuleTrace] = []
    has_fail = False
    has_escalate = False

    for rule in ruleset.rules:
        if not is_rule_applicable(rule, expense):
            continue

        trace = evaluate_rule(rule, expense, budget_state)
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
