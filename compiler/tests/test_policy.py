import json
from typing import Any

import pytest

from compiler.policy import AnswerError, apply_answers, draft_policy
from shared.llm import LLMRequest, LLMResponse

TEXT = (
    "No alcohol. Meals up to $75. Anything over $5,000 needs the finance director. "
    "Never buy from Amazon. Receipts are required for anything over $25. "
    "Hotels up to $200 per night. "
    "Have a great year!"
)


def rule(rule_type: str, quote: str, **kw: Any) -> dict[str, Any]:
    return {
        "rule_type": rule_type,
        "quote": quote,
        "categories": kw.get("categories", []),
        "action": kw.get("action", "unspecified"),
        "approver_role": kw.get("approver_role", ""),
        "merchants": kw.get("merchants", []),
        "questions": kw.get("questions", []),
    }


class Fake:
    def __init__(
        self, rules: list[dict[str, Any]], not_rules: list[dict[str, str]] | None = None
    ) -> None:
        self.text = json.dumps({"rules": rules, "not_rules": not_rules or []})

    def __call__(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text=self.text, model="fake", input_tokens=1, output_tokens=1)


def draft(rules: list[dict[str, Any]], **kw: Any):
    return draft_policy(TEXT, transport=Fake(rules, **kw))


def test_full_policy_becomes_proposed_rules_with_citations() -> None:
    d = draft(
        [
            rule("category_prohibition", "No alcohol.", categories=["alcohol"]),
            rule("per_item_cap", "Meals up to $75.", categories=["meals"], action="review"),
            rule(
                "approval_required",
                "Anything over $5,000 needs the finance director.",
                approver_role="finance_director",
                action="review",
            ),
            rule("merchant_restriction", "Never buy from Amazon.", merchants=["Amazon"]),
            rule("receipt_required", "Receipts are required for anything over $25."),
        ],
        not_rules=[{"quote": "Have a great year!", "why": "Greeting"}],
    )
    assert d.rejected == [] and d.questions == []
    by_type = {r.rule_type: r for r in d.ruleset.rules}
    assert by_type["per_item_cap"].params["cap_cents"] == 7_500
    assert by_type["approval_required"].params["threshold_cents"] == 500_000
    assert by_type["receipt_required"].params["threshold_cents"] == 2_500
    for r in d.ruleset.rules:
        assert r.status == "proposed" and r.source == "policy"
        assert TEXT[r.citation.char_start : r.citation.char_end] == r.citation.quote
    assert d.not_rules[0]["why"] == "Greeting"


def test_amounts_come_from_the_users_words_not_the_model() -> None:
    d = draft([rule("per_item_cap", "Meals up to $75.", categories=["meals"], action="block")])
    assert d.ruleset.rules[0].params["cap_cents"] == 7_500


def test_quote_not_in_text_is_rejected() -> None:
    d = draft([rule("per_item_cap", "Meals up to $150.", categories=["meals"], action="block")])
    assert d.ruleset.rules == []
    assert d.rejected[0]["reason"] == "Quote is not in the policy text"


def test_missing_action_becomes_a_multiple_choice_question() -> None:
    d = draft([rule("per_item_cap", "Meals up to $75.", categories=["meals"])])
    [q] = d.questions
    assert q.field == "action"
    assert {o.value for o in q.options} == {"block", "review"}


def test_model_questions_with_invalid_options_are_dropped() -> None:
    bad_q = {
        "field": "categories",
        "question": "Which?",
        "options": [{"label": "Food", "value": "food"}, {"label": "Snacks", "value": "snacks"}],
    }
    d = draft([rule("category_prohibition", "No alcohol.", questions=[bad_q])])
    assert d.ruleset.rules == []
    assert d.rejected[0]["reason"] == "Couldn't match this to a known cost category"


def test_per_night_limits_are_flagged_as_unsupported() -> None:
    d = draft(
        [
            rule(
                "per_item_cap",
                "Hotels up to $200 per night.",
                categories=["lodging"],
                action="review",
            )
        ]
    )
    assert d.ruleset.rules == []
    assert "period limits" in d.rejected[0]["reason"]


def test_merchants_must_appear_in_the_quote() -> None:
    d = draft([rule("merchant_restriction", "Never buy from Amazon.", merchants=["Walmart"])])
    assert d.rejected[0]["reason"] == "No merchant name found in the rule"


def test_answers_fill_fields_and_are_recorded() -> None:
    d = draft([rule("per_item_cap", "Meals up to $75.", categories=["meals"])])
    q = d.questions[0]
    answered = apply_answers(d, {q.id: "review"})
    r = answered.ruleset.rules[0]
    assert answered.questions == []
    assert r.params["action"] == "review"
    assert r.params["clarifications"] == [
        {"question": q.question, "answer": "Send it to someone to decide"}
    ]


def test_answers_must_be_one_of_the_options() -> None:
    d = draft([rule("per_item_cap", "Meals up to $75.", categories=["meals"])])
    with pytest.raises(AnswerError):
        apply_answers(d, {d.questions[0].id: "approve_everything"})
    with pytest.raises(AnswerError):
        apply_answers(d, {"nope": "review"})


def test_offline_reader_handles_common_phrasings() -> None:
    from compiler.policy import draft_from_items
    from compiler.policy_offline import read_policy

    text = (
        "No alcohol. Meals up to $75. Gifts over $100 require the CEO's approval. "
        "Don't buy from Amazon or Walmart. Receipts over $25. No first class flights. "
        "Hotels up to $250 per night. Submit within 30 days."
    )
    d = draft_from_items({1: text}, "P", read_policy(text), "offline")
    got = {
        (
            r.rule_type,
            tuple(
                r.params.get("categories")
                or r.params.get("prohibited_categories")
                or r.params.get("merchants")
                or []
            ),
        )
        for r in d.ruleset.rules
    }
    assert got == {
        ("category_prohibition", ("alcohol",)),
        ("per_item_cap", ("meals",)),
        ("approval_required", ("gifts",)),
        ("merchant_restriction", ("Amazon", "Walmart")),
        ("receipt_required", ()),
        ("category_prohibition", ("first_class_airfare",)),
    }
    approval = next(r for r in d.ruleset.rules if r.rule_type == "approval_required")
    assert approval.params["approver_role"] == "ceo"
    assert approval.params["threshold_cents"] == 10_000
    assert any("period limits" in x["reason"] for x in d.rejected)
    assert [n["quote"] for n in d.not_rules] == ["Submit within 30 days."]
