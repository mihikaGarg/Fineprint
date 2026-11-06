from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from contracts.base import ContractModel
from contracts.citation import ClauseCitation


class Verdict(StrEnum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class RuleOutcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ESCALATE = "ESCALATE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RuleEvaluation(ContractModel):
    """One line of the clause trace: how a single rule judged the expense."""

    rule_id: str = Field(min_length=1)
    outcome: RuleOutcome
    reason: str = Field(min_length=1)
    citation: ClauseCitation


def aggregate(outcomes: list[RuleOutcome]) -> Verdict:
    """Any FAIL blocks; otherwise any ESCALATE needs review; otherwise allowed."""
    if RuleOutcome.FAIL in outcomes:
        return Verdict.BLOCKED
    if RuleOutcome.ESCALATE in outcomes:
        return Verdict.NEEDS_REVIEW
    return Verdict.ALLOWED


class Decision(ContractModel):
    """ENFORCE output. The verdict must follow from the trace."""

    expense_id: str = Field(min_length=1)
    ruleset_id: str = Field(min_length=1)
    schema_version: str
    verdict: Verdict
    trace: list[RuleEvaluation]

    @model_validator(mode="after")
    def _verdict_follows_trace(self) -> Self:
        expected = aggregate([e.outcome for e in self.trace])
        if self.verdict != expected:
            raise ValueError(f"verdict {self.verdict} does not follow from trace ({expected})")
        return self
