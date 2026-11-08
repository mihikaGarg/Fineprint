from datetime import date
from typing import Any

from contracts.models import (
    BudgetState,
    Expense,
    RuleOutcome,
    RuleTrace,
    SpendRule,
)

# Rule types the engine can evaluate. Grants use the first four; company
# policies can use any of them.
RULE_TYPES = (
    "period_of_performance",
    "category_prohibition",
    "budget_limit",
    "threshold_approval",
    "per_item_cap",
    "approval_required",
    "merchant_restriction",
    "receipt_required",
)


def _format_cents(cents: int) -> str:
    """Format integer cents as dollars, omitting trailing .00 if whole. No float math."""
    dollars, rem = divmod(cents, 100)
    if rem == 0:
        return f"${dollars:,}"
    return f"${dollars:,}.{rem:02d}"


format_cents = _format_cents


def _role_label(role: str) -> str:
    """finance_director -> finance director; cfo -> CFO."""
    return role.upper() if len(role) <= 3 else role.replace("_", " ")


def _category_label(category: str) -> str:
    return category.replace("_", " ")


def _parse_date(val: Any) -> date:
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        return date.fromisoformat(val)
    raise ValueError(f"Cannot parse {val} as date")


def is_rule_applicable(rule: SpendRule, expense: Expense) -> bool:
    """Determine whether a rule applies to the given expense.

    An empty `categories` list means the rule applies to every category.
    """
    params = rule.params

    if "category" in params and params["category"] != expense.category:
        return False
    categories = params.get("categories")
    if categories and expense.category not in categories:
        return False
    if "applies_to" in params and expense.category not in params["applies_to"]:
        return False

    # A budget limit rule applies only to its target budget line or category
    if rule.rule_type == "budget_limit":
        line_key = params.get("budget_line")
        if line_key and line_key != expense.category and "category" not in params:
            return False

    return True


def _trace(rule: SpendRule, outcome: RuleOutcome, reason: str, fix: str | None = None) -> RuleTrace:
    return RuleTrace(
        rule_id=rule.id,
        rule_name=rule.name,
        outcome=outcome,
        reason=reason,
        citation=rule.citation,
        source=rule.source,
        fix=fix if outcome != RuleOutcome.PASS else None,
    )


def evaluate_rule(
    rule: SpendRule,
    expense: Expense,
    budget_state: BudgetState,
) -> RuleTrace:
    """Evaluate a single rule against an expense and budget state.

    Deterministic, pure function, no network or LLM calls. Every FAIL or
    ESCALATE carries a `fix`: what would make this rule pass.
    """
    rule_type = rule.rule_type
    params = rule.params
    amount = expense.amount_cents

    if rule_type == "period_of_performance":
        start_date = _parse_date(params.get("start_date", "1970-01-01"))
        end_date = _parse_date(params.get("end_date", "9999-12-31"))
        label = params.get("label", f"{start_date.isoformat()} - {end_date.isoformat()}")
        if start_date <= expense.date <= end_date:
            return _trace(rule, RuleOutcome.PASS, f"Within {label}")
        return _trace(
            rule,
            RuleOutcome.FAIL,
            f"Date {expense.date.isoformat()} is outside performance period ({label})",
            f"Only expenses dated {label} can be charged here",
        )

    if rule_type == "category_prohibition":
        prohibited = params.get("prohibited_categories", [])
        if expense.category in prohibited and params.get("action") == "review":
            return _trace(
                rule,
                RuleOutcome.ESCALATE,
                f"Category is {_category_label(expense.category)}; only allowed as an exception",
                "A reviewer must confirm this qualifies for the exception",
            )
        if expense.category in prohibited:
            return _trace(
                rule,
                RuleOutcome.FAIL,
                f"Category is {_category_label(expense.category)}",
                "Not allowed in any amount under this rule; use a different funding source",
            )
        return _trace(rule, RuleOutcome.PASS, f"Category '{expense.category}' is not prohibited")

    if rule_type == "category_allowable":
        allowed = params.get("allowed_categories", [])
        if expense.category in allowed:
            return _trace(rule, RuleOutcome.PASS, f"Category '{expense.category}' is allowable")
        return _trace(
            rule,
            RuleOutcome.ESCALATE,
            f"Category '{expense.category}' is not explicitly listed as allowable",
            "A reviewer must confirm this category is allowable",
        )

    if rule_type == "budget_limit":
        line_key = params.get("budget_line", expense.category)
        line = budget_state.lines.get(line_key)
        if not line:
            return _trace(
                rule,
                RuleOutcome.ESCALATE,
                f"No budget line found for '{line_key}'",
                f"Add a '{line_key}' budget line or charge a different line",
            )
        new_spent = line.spent_cents + amount
        if new_spent <= line.allocated_cents:
            return _trace(
                rule,
                RuleOutcome.PASS,
                f"{_format_cents(new_spent)} of {_format_cents(line.allocated_cents)} used",
            )
        remaining = max(0, line.allocated_cents - line.spent_cents)
        return _trace(
            rule,
            RuleOutcome.FAIL,
            (
                f"Exceeds budget line '{line_key}': requires {_format_cents(new_spent)} "
                f"but only {_format_cents(line.allocated_cents)} allocated"
            ),
            f"Only {_format_cents(remaining)} remains on this budget line",
        )

    if rule_type == "threshold_approval":
        threshold_cents = int(params.get("threshold_cents", 0))
        requirement = params.get("requirement", "prior written approval")
        # Clauses read "$X or more", so the threshold itself triggers approval.
        if amount >= threshold_cents:
            if expense.has_prior_approval:
                return _trace(
                    rule,
                    RuleOutcome.PASS,
                    f"Exceeds {_format_cents(threshold_cents)} but {requirement} is verified",
                )
            return _trace(
                rule,
                RuleOutcome.ESCALATE,
                f"Exceeds {_format_cents(threshold_cents)} without {requirement}",
                f"Allowed once {requirement} is attached",
            )
        return _trace(
            rule,
            RuleOutcome.PASS,
            f"Amount {_format_cents(amount)} is below the "
            f"{_format_cents(threshold_cents)} approval threshold",
        )

    if rule_type == "per_item_cap":
        cap = int(params["cap_cents"])
        if amount <= cap:
            return _trace(
                rule,
                RuleOutcome.PASS,
                f"{_format_cents(amount)} is within the {_format_cents(cap)} cap",
            )
        outcome = RuleOutcome.FAIL if params.get("action") == "block" else RuleOutcome.ESCALATE
        return _trace(
            rule,
            outcome,
            f"{_format_cents(amount)} is over the {_format_cents(cap)} cap",
            f"Allowed at {_format_cents(cap)} or less",
        )

    if rule_type == "approval_required":
        threshold_cents = int(params.get("threshold_cents", 0))
        role = str(params["approver_role"])
        if amount < threshold_cents:
            return _trace(
                rule,
                RuleOutcome.PASS,
                f"{_format_cents(amount)} is below the "
                f"{_format_cents(threshold_cents)} approval threshold",
            )
        if role in expense.approvals:
            return _trace(rule, RuleOutcome.PASS, f"Approved by {_role_label(role)}")
        outcome = RuleOutcome.FAIL if params.get("action") == "block" else RuleOutcome.ESCALATE
        return _trace(
            rule,
            outcome,
            f"{_format_cents(amount)} needs {_role_label(role)} approval",
            f"Allowed with approval from the {_role_label(role)}",
        )

    if rule_type == "merchant_restriction":
        merchants: list[str] = params.get("merchants", [])
        merchant = expense.merchant.lower()
        hit = next((m for m in merchants if m.lower() in merchant), None)
        if hit is None:
            return _trace(
                rule, RuleOutcome.PASS, f"'{expense.merchant}' is not a restricted merchant"
            )
        return _trace(
            rule,
            RuleOutcome.FAIL,
            f"'{expense.merchant}' matches restricted merchant '{hit}'",
            "Allowed from a different merchant",
        )

    if rule_type == "receipt_required":
        threshold_cents = int(params.get("threshold_cents", 0))
        if amount < threshold_cents or expense.has_receipt:
            return _trace(rule, RuleOutcome.PASS, "Receipt requirement met")
        return _trace(
            rule,
            RuleOutcome.ESCALATE,
            f"No receipt for {_format_cents(amount)}",
            "Allowed once a receipt is attached",
        )

    # Unknown rule type escalates by safety design
    return _trace(
        rule,
        RuleOutcome.ESCALATE,
        f"Unknown rule type '{rule_type}' requires manual review",
        "A reviewer must decide; this rule type isn't supported",
    )
