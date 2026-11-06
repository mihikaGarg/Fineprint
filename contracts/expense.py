from datetime import date
from typing import Literal

from pydantic import Field

from contracts.base import ContractModel
from contracts.category import ExpenseCategory
from contracts.money import NonNegativeCents, PositiveCents


class Expense(ContractModel):
    """An expense to be checked.

    `category` is assigned before ENFORCE runs; None means it could not be
    determined, and category-dependent rules escalate to NEEDS_REVIEW.
    """

    expense_id: str = Field(min_length=1)
    amount_cents: PositiveCents
    currency: Literal["USD"] = "USD"
    incurred_on: date
    merchant: str = Field(min_length=1)
    description: str = ""
    category: ExpenseCategory | None = None
    budget_line_id: str | None = None
    prior_approval_ref: str | None = None


class BudgetState(ContractModel):
    """Spend already committed against each budget line, before this expense."""

    ruleset_id: str = Field(min_length=1)
    spent_cents_by_line: dict[str, NonNegativeCents] = Field(
        default_factory=dict[str, NonNegativeCents]
    )
