"""Illustrative sample grant used by the API, tests, and web demo.

The ruleset is compiled from SAMPLE_PAGES through the real compiler, so every
citation carries offsets verified against this text.
"""

from compiler.pipeline import compile_pages
from contracts.models import BudgetLine, BudgetState

SAMPLE_GRANT_ID = "grant_bbs_2026"
SAMPLE_GRANT_NAME = "Ramp x BBS Innovation Award"

SAMPLE_PAGES = {
    1: (
        "Ramp x BBS Hackathon Research Award. Grant No. FP-2026-001.\n"
        "Subject to standard federal cost principles."
    ),
    2: (
        "§2.1 Term. The period of performance shall be from January 1, 2026 "
        "through December 31, 2026."
    ),
    7: (
        "§4.2 Travel. Domestic travel necessary to carry out the project is an allowable cost, "
        "subject to the approved budget."
    ),
    12: (
        "§6.1 Unallowable costs. Costs of alcoholic beverages and entertainment are "
        "unallowable under this award."
    ),
    15: (
        "§8.1 Equipment. Equipment expenditures are allowable up to the approved line item "
        "budget.\n§8.3 Special purpose equipment. Capital expenditures for special purpose "
        "equipment having a unit cost of $5,000 or more require prior written approval."
    ),
}

SAMPLE_RULESET, SAMPLE_REJECTED = compile_pages(
    SAMPLE_PAGES, grant_id=SAMPLE_GRANT_ID, grant_name=SAMPLE_GRANT_NAME
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
