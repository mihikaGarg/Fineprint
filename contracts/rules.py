"""Typed rule IR: the output of COMPILE and the input of ENFORCE.

Each rule kind has fixed, deterministic semantics in /enforce. Anything the
compiler cannot express as one of these kinds should not become a rule.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from contracts.base import ContractModel
from contracts.category import ExpenseCategory
from contracts.citation import ClauseCitation, SourceDocument
from contracts.money import PositiveCents


class ThresholdAction(StrEnum):
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"


class RuleBase(ContractModel):
    rule_id: str = Field(min_length=1)
    summary: str = Field(min_length=1, description="Plain-language statement of the rule.")
    citation: ClauseCitation


class CategoryProhibition(RuleBase):
    """Expenses in these categories are unallowable -> BLOCKED."""

    kind: Literal["category_prohibition"] = "category_prohibition"
    categories: list[ExpenseCategory] = Field(min_length=1)


class PeriodOfPerformance(RuleBase):
    """Expenses dated outside [start_date, end_date] (inclusive) -> BLOCKED."""

    kind: Literal["period_of_performance"] = "period_of_performance"
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _start_before_end(self) -> Self:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        return self


class BudgetLineCap(RuleBase):
    """Cumulative spend on a budget line may not exceed cap_cents -> BLOCKED."""

    kind: Literal["budget_line_cap"] = "budget_line_cap"
    budget_line_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    categories: list[ExpenseCategory] = Field(min_length=1)
    cap_cents: PositiveCents


class PerItemThreshold(RuleBase):
    """A single expense at or above threshold_cents triggers `action`.

    Empty `categories` means the threshold applies to every category.
    """

    kind: Literal["per_item_threshold"] = "per_item_threshold"
    categories: list[ExpenseCategory] = Field(default_factory=list[ExpenseCategory])
    threshold_cents: PositiveCents
    action: ThresholdAction


class PriorApprovalRequired(RuleBase):
    """Expenses in these categories need a prior-approval reference, else NEEDS_REVIEW."""

    kind: Literal["prior_approval_required"] = "prior_approval_required"
    categories: list[ExpenseCategory] = Field(min_length=1)


Rule = Annotated[
    CategoryProhibition
    | PeriodOfPerformance
    | BudgetLineCap
    | PerItemThreshold
    | PriorApprovalRequired,
    Field(discriminator="kind"),
]


class Ruleset(ContractModel):
    ruleset_id: str = Field(min_length=1)
    schema_version: str
    grant_id: str = Field(min_length=1)
    source_document: SourceDocument
    rules: list[Rule]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [r.rule_id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("rule_id values must be unique")
        doc_id = self.source_document.document_id
        if any(r.citation.document_id != doc_id for r in self.rules):
            raise ValueError("every citation must reference the ruleset's source document")
        return self
