from datetime import date

import pytest

from compiler.narrow import narrower_scope
from compiler.policy import draft_from_items
from compiler.policy_chat import reply, start_session
from compiler.policy_offline import read_policy
from contracts.models import BudgetState, Expense, RuleOutcome
from enforce.rules import evaluate_rule


@pytest.mark.parametrize(
    ("sentence", "phrase"),
    [
        ("Spousal travel is not reimbursable.", "spousal travel"),
        ("Uber Black is not allowed.", "uber black"),
        ("Purchases from Amazon require procurement approval.", "purchases from Amazon"),
        ("Conference fees over $1,000 require manager sign-off.", "conference fees"),
        ("Gift cards are prohibited.", "gift cards"),
        ("Laptops cost no more than $2,000.", "laptops"),
        ("Wine is not reimbursable.", "wine"),
    ],
)
def test_narrow_rules_are_detected(sentence: str, phrase: str) -> None:
    [item] = read_policy(sentence)["rules"]
    assert narrower_scope(item["quote"], item["rule_type"], item["categories"]) == phrase


@pytest.mark.parametrize(
    "sentence",
    [
        "No alcohol.",
        "Alcohol is not reimbursable except at approved client entertainment events.",
        "Meals up to $75 per person.",
        "No first class flights.",
        "Rideshare and taxi fares up to $100 per ride.",
        "Gifts over $100 require the provost's approval.",
        "Software subscriptions require IT approval.",
        "Expenses of $1,000 or more need manager approval.",
        "Costs of alcoholic beverages and entertainment are unallowable under this award.",
    ],
)
def test_category_wide_rules_are_left_alone(sentence: str) -> None:
    [item] = read_policy(sentence)["rules"]
    assert narrower_scope(item["quote"], item["rule_type"], item["categories"]) is None


def _session(text: str):
    return start_session(draft_from_items({1: text}, "P", read_policy(text), "offline"), "t", [])


def test_narrow_rule_is_held_back_and_asked_about() -> None:
    s = _session("Spousal travel is not reimbursable. No alcohol.")
    assert [r.rule_type for r in s.ruleset.rules] == ["category_prohibition"]  # only alcohol
    gap = next(g for g in s.gaps if g.kind == "narrow")
    assert "only about spousal travel" in gap.prompt
    assert [o.value for o in gap.options] == ["review", "block", "skip"]


def test_choosing_review_applies_it_to_the_category_as_review_only() -> None:
    s = _session("Spousal travel is not reimbursable.")
    gap = next(g for g in s.gaps if g.kind == "narrow")
    s = reply(s, gap.id, "review", None)
    rule = next(
        r for r in s.ruleset.rules if r.citation.quote == "Spousal travel is not reimbursable."
    )
    assert rule.params["action"] == "review"
    assert "not just what the policy names" in rule.params["clarifications"][-1]["question"]


    trace = evaluate_rule(
        rule,
        Expense(
            id="e",
            amount_cents=100,
            date=date(2026, 1, 1),
            merchant="X",
            category="travel_domestic",
        ),
        BudgetState(),
    )
    assert trace.outcome == RuleOutcome.ESCALATE  # flagged for a person, never auto-blocked


def test_skip_creates_no_rule() -> None:
    s = _session("Uber Black is not allowed.")
    gap = next(g for g in s.gaps if g.kind == "narrow")
    s = reply(s, gap.id, "skip", None)
    assert s.ruleset.rules == []
