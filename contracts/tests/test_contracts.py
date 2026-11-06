from datetime import date
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from contracts import (
    SCHEMA_VERSION,
    ClauseCitation,
    Decision,
    Expense,
    PerItemThreshold,
    Rule,
    RuleOutcome,
    Ruleset,
    Verdict,
    aggregate,
)
from contracts.export import SCHEMA_DIR, render

DOC_ID = "grant-001"


def citation(quote: str = "Alcohol is unallowable.") -> dict[str, Any]:
    return {
        "document_id": DOC_ID,
        "page": 3,
        "char_start": 100,
        "char_end": 100 + len(quote),
        "quote": quote,
    }


def ruleset(rules: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "ruleset_id": "rs-1",
        "schema_version": SCHEMA_VERSION,
        "grant_id": "G-1",
        "source_document": {
            "document_id": DOC_ID,
            "filename": "grant.pdf",
            "sha256": "0" * 64,
            "page_count": 10,
        },
        "rules": rules,
    }


PROHIBITION: dict[str, Any] = {
    "kind": "category_prohibition",
    "rule_id": "r1",
    "summary": "No alcohol.",
    "citation": citation(),
    "categories": ["alcohol"],
}


def test_verdict_values() -> None:
    assert {v.value for v in Verdict} == {"ALLOWED", "BLOCKED", "NEEDS_REVIEW"}


def test_citation_span_must_match_quote_length() -> None:
    bad = citation() | {"char_end": 101}
    with pytest.raises(ValidationError):
        ClauseCitation.model_validate(bad)


def test_rule_union_dispatches_on_kind() -> None:
    rule = TypeAdapter[Rule](Rule).validate_python(
        {
            "kind": "per_item_threshold",
            "rule_id": "r2",
            "summary": "Equipment over $5,000 needs review.",
            "citation": citation("over $5,000"),
            "categories": ["equipment"],
            "threshold_cents": 500_000,
            "action": "REVIEW",
        }
    )
    assert isinstance(rule, PerItemThreshold)


@pytest.mark.parametrize("amount", [12.5, 12.0, "1250"])
def test_money_rejects_non_integers(amount: object) -> None:
    with pytest.raises(ValidationError):
        Expense.model_validate(
            {
                "expense_id": "e1",
                "amount_cents": amount,
                "incurred_on": "2026-01-01",
                "merchant": "X",
            }
        )


def test_ruleset_rejects_duplicate_rule_ids() -> None:
    with pytest.raises(ValidationError):
        Ruleset.model_validate(ruleset([PROHIBITION, PROHIBITION]))


def test_ruleset_rejects_citation_to_other_document() -> None:
    foreign = PROHIBITION | {"citation": citation() | {"document_id": "other"}}
    with pytest.raises(ValidationError):
        Ruleset.model_validate(ruleset([foreign]))


def test_ruleset_round_trips_json() -> None:
    rs = Ruleset.model_validate(ruleset([PROHIBITION]))
    assert Ruleset.model_validate_json(rs.model_dump_json()) == rs


@pytest.mark.parametrize(
    ("outcomes", "verdict"),
    [
        ([], Verdict.ALLOWED),
        ([RuleOutcome.PASS, RuleOutcome.NOT_APPLICABLE], Verdict.ALLOWED),
        ([RuleOutcome.PASS, RuleOutcome.ESCALATE], Verdict.NEEDS_REVIEW),
        ([RuleOutcome.ESCALATE, RuleOutcome.FAIL], Verdict.BLOCKED),
    ],
)
def test_aggregate(outcomes: list[RuleOutcome], verdict: Verdict) -> None:
    assert aggregate(outcomes) == verdict


def test_decision_verdict_must_follow_trace() -> None:
    trace = [{"rule_id": "r1", "outcome": "FAIL", "reason": "Alcohol.", "citation": citation()}]
    base = {"expense_id": "e1", "ruleset_id": "rs-1", "schema_version": SCHEMA_VERSION}
    with pytest.raises(ValidationError):
        Decision.model_validate(base | {"verdict": "ALLOWED", "trace": trace})
    decision = Decision.model_validate(base | {"verdict": "BLOCKED", "trace": trace})
    assert decision.verdict is Verdict.BLOCKED


def test_expense_defaults() -> None:
    e = Expense(expense_id="e1", amount_cents=100, incurred_on=date(2026, 1, 1), merchant="X")
    assert e.category is None and e.currency == "USD"


def test_exported_schema_is_up_to_date() -> None:
    for filename, text in render().items():
        path = SCHEMA_DIR / filename
        assert path.exists() and path.read_text() == text, f"{filename} is stale; run `make schema`"
