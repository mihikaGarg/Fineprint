from pathlib import Path

from compiler.budget import read_budget
from compiler.extractor import extract_pdf_pages

DEMO = Path(__file__).resolve().parents[2] / "fixtures" / "grants" / "demo_grant.pdf"


def test_budget_lines_are_read_from_the_exhibit_with_citations() -> None:
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages(DEMO.read_bytes())}
    items = {b.line: b for b in read_budget(pages)}
    assert {k: v.allocated_cents for k, v in items.items()} == {
        "personnel": 6_200_000,
        "travel_domestic": 800_000,
        "equipment": 2_000_000,
        "supplies": 650_000,
    }
    travel = items["travel_domestic"].citation
    assert travel.page == 5 and pages[5][travel.char_start : travel.char_end] == travel.quote


def test_totals_and_non_budget_pages_are_ignored() -> None:
    pages = {
        1: "Meals: $75 per person.",  # no "budget" on this page
        2: "Approved budget\nEquipment: $1,500.50\nTotal direct costs: $1,500.50\nTravel - $900",
    }
    items = {b.line: b.allocated_cents for b in read_budget(pages)}
    assert items == {"equipment": 150_050, "travel_domestic": 90_000}


RESEARCH = Path(__file__).resolve().parents[2] / "fixtures" / "grants" / "research_award.pdf"


def test_table_cells_on_separate_lines_are_paired() -> None:
    # PDF tables often extract as "Label" then "$amount" on the next line.
    pages = {
        1: "Approved Budget\nBudget category\nAmount\nEquipment\n$18,000\nTotal Award\n$263,000"
    }
    (item,) = read_budget(pages)
    assert (item.line, item.allocated_cents) == ("equipment", 1_800_000)
    assert pages[1][item.citation.char_start : item.citation.char_end] == "Equipment\n$18,000"


def test_research_award_budget_table_is_read() -> None:
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages(RESEARCH.read_bytes())}
    items = {b.line: b.allocated_cents for b in read_budget(pages)}
    assert items == {
        "personnel": 13_200_000,
        "fringe": 3_960_000,
        "travel_domestic": 980_000,
        "travel_foreign": 650_000,
        "equipment": 1_800_000,
        "supplies": 1_120_000,
        "participant_support": 1_400_000,
        "contractual": 750_000,
        "other": 340_000,
    }
