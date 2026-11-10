from compiler.coverage import build_coverage
from compiler.examples import examples_for
from compiler.pipeline import compile_pages_full
from contracts import RuleCitation, SpendRule


def _rule(rule_type: str, params: dict[str, object]) -> SpendRule:
    return SpendRule(
        id="r",
        name=rule_type,
        rule_type=rule_type,
        citation=RuleCitation(page=1, quote="x", char_start=0, char_end=1),
        params=params,
        status="proposed",
    )


def test_cap_examples_show_real_engine_verdicts() -> None:
    ex = examples_for(
        _rule("per_item_cap", {"cap_cents": 7_500, "categories": ["meals"], "action": "review"})
    )
    assert [(e.description, e.verdict) for e in ex] == [
        ("$67.50 meal", "ALLOWED"),
        ("$75 meal (exactly the limit)", "ALLOWED"),
        ("$90 meal", "NEEDS_REVIEW"),
    ]
    assert ex[2].fix == "Allowed at $75 or less"


def test_examples_exist_for_every_rule_type() -> None:
    rules = [
        _rule("category_prohibition", {"prohibited_categories": ["alcohol"]}),
        _rule(
            "approval_required",
            {
                "threshold_cents": 500_000,
                "approver_role": "cfo",
                "categories": [],
                "action": "block",
            },
        ),
        _rule("merchant_restriction", {"merchants": ["Amazon"]}),
        _rule("receipt_required", {"threshold_cents": 2_500, "categories": []}),
        _rule("period_of_performance", {"start_date": "2026-01-01", "end_date": "2026-12-31"}),
        _rule("threshold_approval", {"category": "equipment", "threshold_cents": 1_000_000}),
        _rule("budget_limit", {"budget_line": "travel_domestic"}),
    ]
    for r in rules:
        verdicts = {e.verdict for e in examples_for(r)}
        assert "ALLOWED" in verdicts and len(verdicts) >= 2, r.rule_type


def test_coverage_accounts_for_every_clause() -> None:
    pages = {
        1: "The period of performance is March 1, 2026 through June 30, 2026. "
        "Reports are due quarterly to the foundation. "
        "Costs of alcoholic beverages are unallowable.",
    }
    result = compile_pages_full(pages, "g", "G")
    cov = result.coverage
    assert cov.total == 3
    assert (cov.rules, cov.no_rule) == (2, 1)
    assert [c.status for c in cov.clauses] == ["rule", "no_rule", "rule"]


def test_coverage_marks_flagged_and_rejected() -> None:
    pages = {
        1: "The period of performance is set out in the notice. "
        "Travel may be limited by the sponsor."
    }
    result = compile_pages_full(pages, "g", "G")
    flagged = [{"page": 1, "char_start": 52, "char_end": 89, "why": "Unclear limit"}]
    cov = build_coverage(pages, result.ruleset, result.rejected, flagged)
    assert [c.status for c in cov.clauses] == ["rejected", "flagged"]
