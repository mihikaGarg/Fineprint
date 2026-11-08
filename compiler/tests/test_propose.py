from datetime import date

from compiler.pipeline import compile_pages
from compiler.propose import parse_dates, parse_dollars_to_cents, propose_rules


def test_parse_dollars_without_floats() -> None:
    assert parse_dollars_to_cents("a unit cost of $5,000 or more") == 500_000
    assert parse_dollars_to_cents("up to $1,234.56") == 123_456
    assert parse_dollars_to_cents("no amount here") is None


def test_parse_dates() -> None:
    assert parse_dates("from January 1, 2026 through December 31, 2026") == [
        date(2026, 1, 1),
        date(2026, 12, 31),
    ]


def test_period_params_come_from_the_clause() -> None:
    pages = {3: "The period of performance is March 15, 2025 through June 30, 2027."}
    [cand] = propose_rules(pages).candidates
    assert cand.params["start_date"] == "2025-03-15"
    assert cand.params["end_date"] == "2027-06-30"


def test_period_without_dates_is_rejected_not_defaulted() -> None:
    pages = {3: "The period of performance is set out in the notice of award."}
    proposal = propose_rules(pages)
    assert proposal.candidates == []
    assert proposal.rejected[0]["reason"] == "No start and end date found"


def test_threshold_comes_from_the_clause() -> None:
    pages = {9: "Equipment with a unit cost of $10,000 or more requires prior written approval."}
    [cand] = propose_rules(pages).candidates
    assert cand.params["threshold_cents"] == 1_000_000


def test_prohibited_categories_only_those_named() -> None:
    pages = {4: "Costs of alcoholic beverages are unallowable."}
    [cand] = propose_rules(pages).candidates
    assert cand.params["prohibited_categories"] == ["alcohol"]


def test_compiled_citations_verify_against_page_text() -> None:
    pages = {
        2: "§2.1 Term. The period of performance shall be from January 1, 2026\n"
        "through December 31, 2026.",
        12: "Costs of alcoholic beverages are unallowable under this award.",
    }
    ruleset, rejected = compile_pages(pages, grant_id="g", grant_name="G")
    assert rejected == []
    assert len(ruleset.rules) == 2
    for rule in ruleset.rules:
        c = rule.citation
        assert pages[c.page][c.char_start : c.char_end] == c.quote


def test_compile_is_deterministic() -> None:
    pages = {12: "Costs of alcoholic beverages are unallowable under this award."}
    first, _ = compile_pages(pages, grant_id="g", grant_name="G")
    second, _ = compile_pages(pages, grant_id="g", grant_name="G")
    assert first == second
