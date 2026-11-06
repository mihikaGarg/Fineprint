from contracts.models import (
    BudgetLine,
    BudgetState,
    RuleCitation,
    Ruleset,
    SpendRule,
)

SAMPLE_GRANT_NAME = "Ramp x BBS Innovation Award"

SAMPLE_PAGES = {
    1: (
        "Ramp x BBS Hackathon Research Award. Grant No. FP-2026-001.\n"
        "Subject to standard federal cost principles."
    ),
    2: "The period of performance shall be from January 1, 2026 through December 31, 2026.",
    7: (
        "Domestic travel necessary to carry out the project is an allowable cost, "
        "subject to the approved budget."
    ),
    12: "Costs of alcoholic beverages are unallowable under this award.",
    15: (
        "Capital expenditures for special purpose equipment having a unit cost of "
        "$5,000 or more require prior written approval."
    ),
}

SAMPLE_RULESET = Ruleset(
    grant_id="grant_bbs_2026",
    grant_name=SAMPLE_GRANT_NAME,
    rules=[
        SpendRule(
            id="rule_pop",
            name="Period of performance",
            rule_type="period_of_performance",
            citation=RuleCitation(
                page=2,
                quote=(
                    "The period of performance shall be from January 1, 2026 "
                    "through December 31, 2026."
                ),
                prefix="Grant No. FP-2026-001.\n",
                suffix="",
            ),
            params={
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "label": "Jan 1 - Dec 31",
            },
        ),
        SpendRule(
            id="rule_alcohol",
            name="Category prohibition",
            rule_type="category_prohibition",
            citation=RuleCitation(
                page=12,
                quote="Costs of alcoholic beverages are unallowable under this award.",
                prefix="§6.1 Unallowable costs. ",
                suffix="",
            ),
            params={"prohibited_categories": ["alcohol", "entertainment"]},
        ),
        SpendRule(
            id="rule_travel",
            name="Travel budget line",
            rule_type="budget_limit",
            citation=RuleCitation(
                page=7,
                quote=(
                    "Domestic travel necessary to carry out the project is an allowable cost, "
                    "subject to the approved budget."
                ),
                prefix="§4.2 ",
                suffix="",
            ),
            params={"budget_line": "travel_domestic"},
        ),
        SpendRule(
            id="rule_equipment_budget",
            name="Equipment budget line",
            rule_type="budget_limit",
            citation=RuleCitation(
                page=15,
                quote=(
                    "Capital expenditures for special purpose equipment having a unit cost of "
                    "$5,000 or more require prior written approval."
                ),
                prefix="§8.1 ",
                suffix="",
            ),
            params={"budget_line": "equipment"},
        ),
        SpendRule(
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
                suffix="",
            ),
            params={
                "category": "equipment",
                "threshold_cents": 500_000,
                "requirement": "prior written approval from sponsor",
            },
        ),
    ],
)

SAMPLE_BUDGET = BudgetState(
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

SAMPLE_EXPENSES: list[dict[str, str | int | bool]] = [
    {
        "id": "exp_1",
        "merchant": "Lakeshore Hotel",
        "memo": "Conference lodging, 2 nights",
        "amount_cents": 41200,
        "category": "travel_domestic",
        "date": "2026-06-15",
        "has_prior_approval": False,
    },
    {
        "id": "exp_2",
        "merchant": "Riverside Wine Bar",
        "memo": "Team dinner",
        "amount_cents": 18640,
        "category": "alcohol",
        "date": "2026-06-16",
        "has_prior_approval": False,
    },
    {
        "id": "exp_3",
        "merchant": "Meridian Optics",
        "memo": "Thermal imaging camera",
        "amount_cents": 625000,
        "category": "equipment",
        "date": "2026-07-01",
        "has_prior_approval": False,
    },
    {
        "id": "exp_4",
        "merchant": "Meridian Optics",
        "memo": "Thermal imaging camera (with approval)",
        "amount_cents": 625000,
        "category": "equipment",
        "date": "2026-07-01",
        "has_prior_approval": True,
    },
]
