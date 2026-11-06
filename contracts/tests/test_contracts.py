from datetime import date

import pytest
from pydantic import ValidationError

from contracts import (
    SCHEMA_VERSION,
    BudgetLine,
    EnforcementResult,
    Expense,
    RuleCitation,
    RuleOutcome,
    Ruleset,
    RuleTrace,
    SpendRule,
    Verdict,
)


def test_schema_version_is_semver() -> None:
    assert len(SCHEMA_VERSION.split(".")) == 3
    assert SCHEMA_VERSION == "0.2.0"


def test_verdict_values() -> None:
    assert {v.value for v in Verdict} == {"ALLOWED", "BLOCKED", "NEEDS_REVIEW"}


def test_rule_outcome_values() -> None:
    assert {o.value for o in RuleOutcome} == {"PASS", "FAIL", "ESCALATE"}


def test_expense_validation() -> None:
    valid_expense = Expense(
        id="exp_1",
        amount_cents=5000,
        date=date(2026, 4, 15),
        merchant="Acme Supplies",
        category="supplies",
        memo="Lab equipment parts",
    )
    assert valid_expense.amount_cents == 5000

    # Negative cents must fail validation
    with pytest.raises(ValidationError):
        Expense(
            id="exp_invalid",
            amount_cents=-100,
            date=date(2026, 4, 15),
            merchant="Acme Supplies",
            category="supplies",
        )


def test_budget_line_validation() -> None:
    line = BudgetLine(category="travel", allocated_cents=100000, spent_cents=45000)
    assert line.allocated_cents == 100000
    assert line.spent_cents == 45000

    with pytest.raises(ValidationError):
        BudgetLine(category="travel", allocated_cents=-50)


def test_models_json_serialization() -> None:
    citation = RuleCitation(
        page=7,
        quote="Domestic travel necessary to carry out the project is an allowable cost",
        char_start=120,
        char_end=194,
    )
    rule = SpendRule(
        id="rule_travel",
        name="Travel budget line",
        rule_type="budget_limit",
        citation=citation,
        params={"budget_line": "travel_domestic"},
    )
    ruleset = Ruleset(
        grant_id="grant_123",
        grant_name="National Science Award",
        rules=[rule],
    )
    assert ruleset.grant_id == "grant_123"
    result = EnforcementResult(
        verdict=Verdict.ALLOWED,
        traces=[
            RuleTrace(
                rule_id=rule.id,
                rule_name=rule.name,
                outcome=RuleOutcome.PASS,
                reason="$3,612 of $8,000 used",
                citation=citation,
            )
        ],
        latency_ms=0.45,
    )

    # Test roundtrip serialization to JSON
    json_data = result.model_dump_json()
    restored = EnforcementResult.model_validate_json(json_data)
    assert restored.verdict == Verdict.ALLOWED
    assert len(restored.traces) == 1
    assert restored.traces[0].citation.page == 7
