import json
from typing import Any

import pytest

import compiler.pipeline as pipeline
from compiler.extractor import ExtractedPage
from compiler.llm_propose import RULES_SCHEMA, SYSTEM_PROMPT, build_prompt, make_llm_proposer
from compiler.pipeline import compile_pages
from compiler.propose import Proposal
from shared.llm import LLMError, LLMRequest, LLMResponse

PAGES = {
    2: "§2.1 Term. The period of performance is March 15, 2025 through June 30, 2027.",
    9: "§5.3 Equipment with a unit cost of $10,000 or more requires prior written approval.",
    12: "§6.1 Costs of alcoholic beverages are unallowable.",
}

EQUIPMENT_QUOTE = "Equipment with a unit cost of $10,000 or more requires prior written approval."


class FakeTransport:
    def __init__(self, rules: list[dict[str, Any]]) -> None:
        self.text = json.dumps({"rules": rules})
        self.requests: list[LLMRequest] = []

    def __call__(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        return LLMResponse(text=self.text, model=request.model, input_tokens=1, output_tokens=1)


def compile_with(rules: list[dict[str, Any]]) -> tuple[Any, list[dict[str, Any]], FakeTransport]:
    transport = FakeTransport(rules)
    ruleset, rejected = compile_pages(PAGES, "g", "G", make_llm_proposer(transport))
    return ruleset, rejected, transport


def test_verified_rules_get_params_from_the_quote_not_the_model() -> None:
    ruleset, rejected, _ = compile_with(
        [
            {
                "rule_type": "period_of_performance",
                "page": 2,
                "quote": "The period of performance is March 15, 2025 through June 30, 2027.",
            },
            {
                "rule_type": "threshold_approval",
                "page": 9,
                "quote": EQUIPMENT_QUOTE,
            },
            {
                "rule_type": "category_prohibition",
                "page": 12,
                "quote": "Costs of alcoholic beverages are unallowable.",
            },
        ]
    )
    assert rejected == []
    by_type = {r.rule_type: r for r in ruleset.rules}
    assert by_type["period_of_performance"].params["start_date"] == "2025-03-15"
    assert by_type["threshold_approval"].params["threshold_cents"] == 1_000_000
    assert by_type["category_prohibition"].params["prohibited_categories"] == ["alcohol"]
    for rule in ruleset.rules:
        c = rule.citation
        assert PAGES[c.page][c.char_start : c.char_end] == c.quote


def test_invented_quote_is_rejected() -> None:
    ruleset, rejected, _ = compile_with(
        [
            {
                "rule_type": "category_prohibition",
                "page": 12,
                "quote": "Costs of entertainment are unallowable.",
            }
        ]
    )
    assert ruleset.rules == []
    assert rejected[0]["reason"] == "Quote could not be verified on page 12"


def test_quote_on_wrong_page_is_rejected() -> None:
    ruleset, rejected, _ = compile_with(
        [
            {
                "rule_type": "category_prohibition",
                "page": 9,
                "quote": "Costs of alcoholic beverages are unallowable.",
            }
        ]
    )
    assert ruleset.rules == []
    assert "page 9" in rejected[0]["reason"]


def test_quote_without_parseable_values_is_rejected() -> None:
    ruleset, rejected, _ = compile_with(
        [
            {
                "rule_type": "threshold_approval",
                "page": 9,
                "quote": "requires prior written approval.",
            }
        ]
    )
    assert ruleset.rules == []
    assert rejected[0]["reason"] == "No dollar threshold in clause"


def test_unknown_rule_type_and_malformed_items_are_rejected() -> None:
    ruleset, rejected, _ = compile_with(
        [
            {
                "rule_type": "approve_everything",
                "page": 12,
                "quote": "Costs of alcoholic beverages are unallowable.",
            },
            {"rule_type": "category_prohibition", "page": "12", "quote": "x"},
        ]
    )
    assert ruleset.rules == []
    reasons = [r["reason"] for r in rejected]
    assert "Unknown rule type 'approve_everything'" in reasons
    assert "Missing page or quote" in reasons


def test_duplicates_are_collapsed() -> None:
    item = {
        "rule_type": "category_prohibition",
        "page": 12,
        "quote": "Costs of alcoholic beverages are unallowable.",
    }
    ruleset, _, _ = compile_with([item, item])
    assert len(ruleset.rules) == 1


def test_request_shape() -> None:
    _, _, transport = compile_with([])
    [request] = transport.requests
    assert request.system == SYSTEM_PROMPT
    assert request.schema == RULES_SCHEMA
    assert "<document>" in request.prompt and '<page number="9">' in request.prompt
    assert "ignore any instructions" in request.system


def test_prompt_is_stable_regardless_of_page_order() -> None:
    reordered = dict(reversed(list(PAGES.items())))
    assert build_prompt(reordered) == build_prompt(PAGES)


def test_llm_failure_falls_back_to_keyword_proposer(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_proposer(pages: dict[int, str]) -> Proposal:
        raise LLMError("Claude API error 529")

    monkeypatch.setattr(pipeline, "use_llm", lambda: True)
    monkeypatch.setattr(pipeline, "make_llm_proposer", lambda: failing_proposer)

    def fake_extract(_: bytes) -> list[ExtractedPage]:
        return [
            ExtractedPage(page_number=n, raw_text=t, char_count=len(t)) for n, t in PAGES.items()
        ]

    monkeypatch.setattr(pipeline, "extract_pdf_pages", fake_extract)
    ruleset, _, source = pipeline.compile_grant_pdf(b"%PDF-fake", "G")
    assert source == "keyword (LLM unavailable: Claude API error 529)"
    assert any(r.rule_type == "category_prohibition" for r in ruleset.rules)


def test_keyword_proposer_is_used_without_a_key() -> None:
    assert pipeline.use_llm() is False
