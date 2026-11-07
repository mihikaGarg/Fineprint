from datetime import date
from typing import Any

from contracts.models import (
    BudgetState,
    Expense,
    RuleOutcome,
    RuleTrace,
    SpendRule,
)


def _format_cents(cents: int) -> str:
    """Format integer cents as dollars, omitting trailing .00 if whole. No float math."""
    dollars, rem = divmod(cents, 100)
    if rem == 0:
        return f"${dollars:,}"
    return f"${dollars:,}.{rem:02d}"


def _parse_date(val: Any) -> date:
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val)
    raise ValueError(f"Cannot parse {val} as date")


def is_rule_applicable(rule: SpendRule, expense: Expense) -> bool:
    """Determine whether a rule applies to the given expense."""
    params = rule.params

    # Explicit category constraints
    if "category" in params and params["category"] != expense.category:
        return False
    if "categories" in params and expense.category not in params["categories"]:
        return False
    if "applies_to" in params and expense.category not in params["applies_to"]:
        return False

    # A budget limit rule applies only to its target budget line or category
    if rule.rule_type == "budget_limit":
        line_key = params.get("budget_line")
        if line_key and line_key != expense.category and "category" not in params:
            return False

    return True


def evaluate_rule(
    rule: SpendRule,
    expense: Expense,
    budget_state: BudgetState,
) -> RuleTrace:
    """Evaluate a single rule against an expense and budget state.

    Deterministic, pure function, no network or LLM calls.
    """
    rule_type = rule.rule_type
    params = rule.params

    if rule_type == "period_of_performance":
        start_date = _parse_date(params.get("start_date", "1970-01-01"))
        end_date = _parse_date(params.get("end_date", "9999-12-31"))
        label = params.get("label", f"{start_date.isoformat()} - {end_date.isoformat()}")

        if start_date <= expense.date <= end_date:
            return RuleTrace(
                rule_id=rule.id,
                rule_name=rule.name,
                outcome=RuleOutcome.PASS,
                reason=f"Within {label}",
                citation=rule.citation,
            )
        return RuleTrace(
            rule_id=rule.id,
            rule_name=rule.name,
            outcome=RuleOutcome.FAIL,
            reason=f"Date {expense.date.isoformat()} is outside performance period ({label})",
            citation=rule.citation,
        )

    elif rule_type == "category_prohibition":
        prohibited = params.get("prohibited_categories", [])
        if expense.category in prohibited:
            return RuleTrace(
                rule_id=rule.id,
                rule_name=rule.name,
                outcome=RuleOutcome.FAIL,
                reason=f"Category is {expense.category}",
                citation=rule.citation,
            )
        return RuleTrace(
            rule_id=rule.id,
            rule_name=rule.name,
            outcome=RuleOutcome.PASS,
            reason=f"Category '{expense.category}' is not prohibited",
            citation=rule.citation,
        )

    elif rule_type == "category_allowable":
        allowed = params.get("allowed_categories", [])
        if expense.category in allowed:
            return RuleTrace(
                rule_id=rule.id,
                rule_name=rule.name,
                outcome=RuleOutcome.PASS,
                reason=f"Category '{expense.category}' is allowable",
                citation=rule.citation,
            )
        return RuleTrace(
            rule_id=rule.id,
            rule_name=rule.name,
            outcome=RuleOutcome.ESCALATE,
            reason=f"Category '{expense.category}' is not explicitly listed as allowable",
            citation=rule.citation,
        )

    elif rule_type == "budget_limit":
        line_key = params.get("budget_line", expense.category)
        line = budget_state.lines.get(line_key)
        if not line:
            return RuleTrace(
                rule_id=rule.id,
                rule_name=rule.name,
                outcome=RuleOutcome.ESCALATE,
                reason=f"No budget line found for '{line_key}'",
                citation=rule.citation,
            )

        new_spent = line.spent_cents + expense.amount_cents
        if new_spent <= line.allocated_cents:
            return RuleTrace(
                rule_id=rule.id,
                rule_name=rule.name,
                outcome=RuleOutcome.PASS,
                reason=f"{_format_cents(new_spent)} of {_format_cents(line.allocated_cents)} used",
                citation=rule.citation,
            )
        return RuleTrace(
            rule_id=rule.id,
            rule_name=rule.name,
            outcome=RuleOutcome.FAIL,
            reason=(
                f"Exceeds budget line '{line_key}': requires {_format_cents(new_spent)} "
                f"but only {_format_cents(line.allocated_cents)} allocated"
            ),
            citation=rule.citation,
        )

    elif rule_type == "threshold_approval":
        threshold_cents = int(params.get("threshold_cents", 0))
        requirement = params.get("requirement", "prior written approval")

        # Clauses read "$X or more", so the threshold itself triggers approval.
        if expense.amount_cents >= threshold_cents:
            if expense.has_prior_approval:
                return RuleTrace(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    outcome=RuleOutcome.PASS,
                    reason=(
                        f"Exceeds {_format_cents(threshold_cents)} but {requirement} is verified"
                    ),
                    citation=rule.citation,
                )
            return RuleTrace(
                rule_id=rule.id,
                rule_name=rule.name,
                outcome=RuleOutcome.ESCALATE,
                reason=f"Exceeds {_format_cents(threshold_cents)} without {requirement}",
                citation=rule.citation,
            )
        return RuleTrace(
            rule_id=rule.id,
            rule_name=rule.name,
            outcome=RuleOutcome.PASS,
            reason=(
                f"Amount {_format_cents(expense.amount_cents)} is below the "
                f"{_format_cents(threshold_cents)} approval threshold"
            ),
            citation=rule.citation,
        )

    # Unknown rule type escalates by safety design
    return RuleTrace(
        rule_id=rule.id,
        rule_name=rule.name,
        outcome=RuleOutcome.ESCALATE,
        reason=f"Unknown rule type '{rule_type}' requires manual review",
        citation=rule.citation,
    )
