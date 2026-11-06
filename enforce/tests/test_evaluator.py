import time
from datetime import date

from contracts import (
    BudgetLine,
    BudgetState,
    Expense,
    RuleCitation,
    RuleOutcome,
    Ruleset,
    SpendRule,
    Verdict,
)
from enforce import evaluate_expense


def _build_sample_ruleset() -> Ruleset:
    period_rule = SpendRule(
        id="rule_pop",
        name="Period of performance",
        rule_type="period_of_performance",
        citation=RuleCitation(
            page=2,
            quote=(
                "The period of performance shall be from January 1, 2026 through December 31, 2026."
            ),
        ),
        params={"start_date": "2026-01-01", "end_date": "2026-12-31", "label": "Jan 1 - Dec 31"},
    )

    alcohol_rule = SpendRule(
        id="rule_alcohol",
        name="Category prohibition",
        rule_type="category_prohibition",
        citation=RuleCitation(
            page=12,
            quote="Costs of alcoholic beverages are unallowable under this award.",
            prefix="§6.1 Unallowable costs. ",
        ),
        params={"prohibited_categories": ["alcohol", "entertainment"]},
    )

    travel_budget_rule = SpendRule(
        id="rule_travel_budget",
        name="Travel budget line",
        rule_type="budget_limit",
        citation=RuleCitation(
            page=7,
            quote=(
                "Domestic travel necessary to carry out the project is an allowable cost, "
                "subject to the approved budget."
            ),
            prefix="§4.2 ",
        ),
        params={"budget_line": "travel_domestic"},
    )

    equipment_budget_rule = SpendRule(
        id="rule_equipment_budget",
        name="Equipment budget line",
        rule_type="budget_limit",
        citation=RuleCitation(
            page=15,
            quote="Equipment expenditures are allowable up to the approved line item budget.",
            prefix="§8.1 ",
        ),
        params={"budget_line": "equipment"},
    )

    equipment_approval_rule = SpendRule(
        id="rule_equipment_approval",
        name="Equipment prior approval",
        rule_type="threshold_approval",
        citation=RuleCitation(
            page=15,
            quote=(
                "Capital expenditures for special purpose equipment having a unit cost of "
                "$5,000 or more require prior written approval."
            ),
            prefix="§8.3 Equipment. ",
        ),
        params={
            "category": "equipment",
            "threshold_cents": 500_000,
            "requirement": "prior written approval from sponsor",
        },
    )

    return Ruleset(
        grant_id="grant_bbs_2026",
        grant_name="Research Excellence Award",
        rules=[
            period_rule,
            alcohol_rule,
            travel_budget_rule,
            equipment_budget_rule,
            equipment_approval_rule,
        ],
    )


def _build_sample_budget() -> BudgetState:
    return BudgetState(
        lines={
            "travel_domestic": BudgetLine(
                category="travel_domestic",
                allocated_cents=800_000,
                spent_cents=320_000,
            ),
            "equipment": BudgetLine(
                category="equipment",
                allocated_cents=2_000_000,
                spent_cents=0,
            ),
        }
    )


def test_allowed_expense_flow() -> None:
    ruleset = _build_sample_ruleset()
    budget = _build_sample_budget()

    # $412.00 lodging
    expense = Expense(
        id="exp_hotel",
        amount_cents=41_200,
        date=date(2026, 6, 15),
        merchant="Lakeshore Hotel",
        category="travel_domestic",
        memo="Conference lodging, 2 nights",
    )

    result = evaluate_expense(expense, ruleset, budget)
    assert result.verdict == Verdict.ALLOWED
    # Traces evaluated: Period of performance, Category prohibition, Travel budget line
    assert len(result.traces) == 3
    assert all(t.outcome == RuleOutcome.PASS for t in result.traces)

    # Check budget trace output
    travel_trace = next(t for t in result.traces if t.rule_id == "rule_travel_budget")
    assert travel_trace.outcome == RuleOutcome.PASS
    assert "$3,612 of $8,000 used" in travel_trace.reason


def test_blocked_prohibited_category() -> None:
    ruleset = _build_sample_ruleset()
    budget = _build_sample_budget()

    # $186.40 team dinner with alcohol
    expense = Expense(
        id="exp_alcohol",
        amount_cents=18_640,
        date=date(2026, 6, 16),
        merchant="Riverside Wine Bar",
        category="alcohol",
        memo="Team dinner",
    )

    result = evaluate_expense(expense, ruleset, budget)
    assert result.verdict == Verdict.BLOCKED

    prohibition_trace = next(t for t in result.traces if t.rule_id == "rule_alcohol")
    assert prohibition_trace.outcome == RuleOutcome.FAIL
    assert prohibition_trace.citation.page == 12
    assert "Costs of alcoholic beverages are unallowable" in prohibition_trace.citation.quote


def test_needs_review_threshold_approval_missing() -> None:
    ruleset = _build_sample_ruleset()
    budget = _build_sample_budget()

    # $6,250.00 thermal imaging camera without approval
    expense = Expense(
        id="exp_camera",
        amount_cents=625_000,
        date=date(2026, 7, 1),
        merchant="Meridian Optics",
        category="equipment",
        memo="Thermal imaging camera",
        has_prior_approval=False,
    )

    result = evaluate_expense(expense, ruleset, budget)
    assert result.verdict == Verdict.NEEDS_REVIEW

    # Period of performance + Equipment budget line passed
    pop_trace = next(t for t in result.traces if t.rule_id == "rule_pop")
    assert pop_trace.outcome == RuleOutcome.PASS

    eq_budget_trace = next(t for t in result.traces if t.rule_id == "rule_equipment_budget")
    assert eq_budget_trace.outcome == RuleOutcome.PASS
    assert "$6,250 of $20,000 used" in eq_budget_trace.reason

    # Prior approval escalated
    approval_trace = next(t for t in result.traces if t.rule_id == "rule_equipment_approval")
    assert approval_trace.outcome == RuleOutcome.ESCALATE
    assert "prior written approval from sponsor" in approval_trace.reason


def test_allowed_when_prior_approval_present() -> None:
    ruleset = _build_sample_ruleset()
    budget = _build_sample_budget()

    # $6,250.00 thermal imaging camera WITH approval
    expense = Expense(
        id="exp_camera_approved",
        amount_cents=625_000,
        date=date(2026, 7, 1),
        merchant="Meridian Optics",
        category="equipment",
        memo="Thermal imaging camera",
        has_prior_approval=True,
    )

    result = evaluate_expense(expense, ruleset, budget)
    assert result.verdict == Verdict.ALLOWED

    approval_trace = next(t for t in result.traces if t.rule_id == "rule_equipment_approval")
    assert approval_trace.outcome == RuleOutcome.PASS


def test_blocked_when_date_outside_period() -> None:
    ruleset = _build_sample_ruleset()
    budget = _build_sample_budget()

    expense = Expense(
        id="exp_pre_grant",
        amount_cents=10_000,
        date=date(2025, 12, 31),
        merchant="Lakeshore Hotel",
        category="travel_domestic",
    )

    result = evaluate_expense(expense, ruleset, budget)
    assert result.verdict == Verdict.BLOCKED
    pop_trace = next(t for t in result.traces if t.rule_id == "rule_pop")
    assert pop_trace.outcome == RuleOutcome.FAIL


def test_blocked_when_exceeding_budget() -> None:
    ruleset = _build_sample_ruleset()
    budget = _build_sample_budget()

    # Travel allocation is 800_000 ($8,000), spent is 320_000 ($3,200).
    # Expense of $5,000 (500_000) brings total to $8,200, exceeding $8,000.
    expense = Expense(
        id="exp_large_flight",
        amount_cents=500_000,
        date=date(2026, 8, 10),
        merchant="Global Airways",
        category="travel_domestic",
    )

    result = evaluate_expense(expense, ruleset, budget)
    assert result.verdict == Verdict.BLOCKED
    budget_trace = next(t for t in result.traces if t.rule_id == "rule_travel_budget")
    assert budget_trace.outcome == RuleOutcome.FAIL


def test_escalates_when_budget_line_is_missing() -> None:
    ruleset = _build_sample_ruleset()
    budget = BudgetState(lines={})  # empty budget

    expense = Expense(
        id="exp_travel",
        amount_cents=10_000,
        date=date(2026, 5, 1),
        merchant="Trainline",
        category="travel_domestic",
    )

    result = evaluate_expense(expense, ruleset, budget)
    assert result.verdict == Verdict.NEEDS_REVIEW
    budget_trace = next(t for t in result.traces if t.rule_id == "rule_travel_budget")
    assert budget_trace.outcome == RuleOutcome.ESCALATE


def test_latency_microbenchmark() -> None:
    ruleset = _build_sample_ruleset()
    budget = _build_sample_budget()
    expense = Expense(
        id="exp_bench",
        amount_cents=41_200,
        date=date(2026, 6, 15),
        merchant="Lakeshore Hotel",
        category="travel_domestic",
    )

    # Warmup
    for _ in range(10):
        evaluate_expense(expense, ruleset, budget)

    n_runs = 500
    t0 = time.perf_counter()
    for _ in range(n_runs):
        res = evaluate_expense(expense, ruleset, budget)
        assert res.verdict == Verdict.ALLOWED
    t1 = time.perf_counter()

    avg_ms = ((t1 - t0) / n_runs) * 1000.0
    # Strict benchmark: must be well under 5ms (contract requires <100ms)
    assert avg_ms < 5.0, f"Average latency too high: {avg_ms:.3f}ms"
