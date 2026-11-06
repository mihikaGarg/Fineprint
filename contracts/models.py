from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from contracts.verdict import Verdict


class RuleOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ESCALATE = "ESCALATE"


class RuleCitation(BaseModel):
    page: int
    quote: str
    char_start: int | None = None
    char_end: int | None = None
    prefix: str = ""
    suffix: str = ""


class Expense(BaseModel):
    id: str
    amount_cents: int
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
    allocated_cents: int
    spent_cents: int = 0

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
    rules: list[SpendRule] = Field(default_factory=list)


class RuleTrace(BaseModel):
    rule_id: str
    rule_name: str
    outcome: RuleOutcome
    reason: str
    citation: RuleCitation


class EnforcementResult(BaseModel):
    verdict: Verdict
    traces: list[RuleTrace] = Field(default_factory=list)
    latency_ms: float = 0.0
