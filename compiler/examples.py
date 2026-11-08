"""Auto-generated examples for rule cards.

Each example is a synthetic expense run through the real enforce engine
against that one rule, so the verdict shown to the reviewer is exactly what
enforcement will do. Reviewers check a rule by looking at examples like
"$90 dinner -> NEEDS_REVIEW" instead of reading parameters.
"""

from datetime import date, timedelta

from pydantic import BaseModel

from contracts.models import BudgetLine, BudgetState, Expense, Ruleset, SpendRule
from enforce.engine import evaluate_expense
from enforce.rules import format_cents as _format_cents

DEFAULT_DATE = date(2026, 6, 15)


class RuleExample(BaseModel):
    description: str
    expense: Expense
    verdict: str
    reason: str
    fix: str | None = None


def _expense(
    rule: SpendRule,
    amount_cents: int,
    *,
    category: str | None = None,
    merchant: str = "Example Vendor",
    on: date = DEFAULT_DATE,
    approvals: list[str] | None = None,
    has_prior_approval: bool = False,
    has_receipt: bool = False,
) -> Expense:
    params = rule.params
    cats: list[str] = (
        params.get("categories")
        or params.get("prohibited_categories")
        or ([params["category"]] if "category" in params else [])
        or ([params["budget_line"]] if "budget_line" in params else [])
    )
    return Expense(
        id="example",
        amount_cents=amount_cents,
        date=on,
        merchant=merchant,
        category=category or (cats[0] if cats else "supplies"),
        approvals=approvals or [],
        has_prior_approval=has_prior_approval,
        has_receipt=has_receipt,
    )


def _cases(rule: SpendRule) -> list[tuple[str, Expense]]:
    p = rule.params
    t = rule.rule_type
    if t == "per_item_cap":
        cap = int(p["cap_cents"])
        under, over = cap * 9 // 10, cap * 6 // 5
        return [
            (f"{_format_cents(under)} expense", _expense(rule, under)),
            (f"{_format_cents(cap)} expense (exactly the cap)", _expense(rule, cap)),
            (f"{_format_cents(over)} expense", _expense(rule, over)),
        ]
    if t in ("approval_required", "threshold_approval"):
        threshold = max(int(p.get("threshold_cents", 0)), 100)
        role = p.get("approver_role")
        over = threshold * 6 // 5
        approved = (
            _expense(rule, over, approvals=[role])
            if role
            else _expense(rule, over, has_prior_approval=True)
        )
        who = str(role).replace("_", " ") if role else "prior written"
        cases = [
            (f"{_format_cents(over)}, no approval", _expense(rule, over)),
            (f"{_format_cents(over)}, with {who} approval", approved),
        ]
        if int(p.get("threshold_cents", 0)) > 0:
            under = threshold * 9 // 10
            cases.insert(0, (f"{_format_cents(under)}, no approval", _expense(rule, under)))
        return cases
    if t == "category_prohibition":
        banned = p.get("prohibited_categories") or ["alcohol"]
        allowed = next(c for c in ("supplies", "software", "other") if c not in banned)
        return [
            (f"$50 {banned[0].replace('_', ' ')}", _expense(rule, 5_000, category=banned[0])),
            (f"$50 {allowed}", _expense(rule, 5_000, category=allowed)),
        ]
    if t == "merchant_restriction":
        m = p["merchants"][0]
        return [
            (f"$40 at {m}", _expense(rule, 4_000, merchant=m)),
            ("$40 at another merchant", _expense(rule, 4_000, merchant="Corner Office Supply")),
        ]
    if t == "receipt_required":
        threshold = max(int(p.get("threshold_cents", 0)), 100)
        return [
            (f"{_format_cents(threshold)}, no receipt", _expense(rule, threshold)),
            (
                f"{_format_cents(threshold)}, receipt attached",
                _expense(rule, threshold, has_receipt=True),
            ),
        ]
    if t == "period_of_performance":
        start = date.fromisoformat(p["start_date"])
        end = date.fromisoformat(p["end_date"])
        return [
            ("$100 on the first day", _expense(rule, 10_000, on=start)),
            ("$100 the day after it ends", _expense(rule, 10_000, on=end + timedelta(days=1))),
        ]
    if t == "budget_limit":
        line = p.get("budget_line", "supplies")
        return [
            ("$100 with budget left", _expense(rule, 10_000, category=line)),
            ("$1,000 when only $500 remains", _expense(rule, 100_000, category=line)),
        ]
    return []


def examples_for(rule: SpendRule) -> list[RuleExample]:
    approved = rule.model_copy(update={"status": "approved"})
    ruleset = Ruleset(grant_id="example", grant_name="example", rules=[approved])
    out: list[RuleExample] = []
    for description, expense in _cases(rule):
        budget = BudgetState()
        if rule.rule_type == "budget_limit":
            line = expense.category
            spent = 50_000 if expense.amount_cents > 50_000 else 0
            budget = BudgetState(
                lines={line: BudgetLine(category=line, allocated_cents=100_000, spent_cents=spent)}
            )
        result = evaluate_expense(expense, ruleset, budget)
        trace = result.traces[0] if result.traces else None
        out.append(
            RuleExample(
                description=description,
                expense=expense,
                verdict=result.verdict.value,
                reason=trace.reason if trace else "Rule does not apply",
                fix=trace.fix if trace else None,
            )
        )
    return out
