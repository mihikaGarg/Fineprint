from datetime import date
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, Field, StrictInt, field_validator, model_validator

from contracts.verdict import Verdict


class RuleOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ESCALATE = "ESCALATE"


class RuleCitation(BaseModel):
    """Verbatim clause span: page_text[char_start:char_end] == quote on a 1-based page."""

    page: int = Field(ge=1)
    quote: str = Field(min_length=1)
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=1)
    prefix: str = ""
    suffix: str = ""

    @model_validator(mode="after")
    def _span_matches_quote(self) -> Self:
        if self.char_end - self.char_start != len(self.quote):
            raise ValueError("char_end - char_start must equal len(quote)")
        return self


class Expense(BaseModel):
    id: str
    amount_cents: StrictInt
    date: date
    merchant: str
    category: str
    memo: str = ""
    has_prior_approval: bool = False

    @field_validator("amount_cents")
    @classmethod
    def validate_amount_cents(cls, v: int) -> int:
        if v < 0:
            raise ValueError("amount_cents must be non-negative")
        return v


class BudgetLine(BaseModel):
    category: str
    allocated_cents: StrictInt
    spent_cents: StrictInt = 0

    @field_validator("allocated_cents", "spent_cents")
    @classmethod
    def validate_cents(cls, v: int) -> int:
        if v < 0:
            raise ValueError("cents must be non-negative")
        return v


class BudgetState(BaseModel):
    lines: dict[str, BudgetLine] = Field(default_factory=dict)


class SpendRule(BaseModel):
    id: str
    name: str
    rule_type: str
    citation: RuleCitation
    params: dict[str, Any] = Field(default_factory=dict)


class Ruleset(BaseModel):
    grant_id: str
    grant_name: str
    rules: list[SpendRule] = Field(default_factory=list[SpendRule])


class RuleTrace(BaseModel):
    rule_id: str
    rule_name: str
    outcome: RuleOutcome
    reason: str
    citation: RuleCitation


class EnforcementResult(BaseModel):
    verdict: Verdict
    traces: list[RuleTrace] = Field(default_factory=list[RuleTrace])
    latency_ms: float = 0.0
