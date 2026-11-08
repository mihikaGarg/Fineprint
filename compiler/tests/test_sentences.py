from pathlib import Path

import pytest

from compiler.extractor import extract_pdf_pages
from compiler.sentences import split_sentences

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def texts(t: str) -> list[str]:
    return [s.text for s in split_sentences(t)]


def test_wrapped_lines_stay_in_one_sentence() -> None:
    first_line = (
        "Costs incurred outside the period of performance may not be charged "
        "to the award unless the"
    )
    wrapped = first_line + "\nFoundation agrees in writing."
    assert texts(wrapped + " Next sentence.") == [wrapped, "Next sentence."]


@pytest.mark.parametrize(
    "text",
    ["Award Agreement No. CCR-2026-014", "See e.g. the U.S. rules.", "Policy (FIN-204, rev. 7)"],
)
def test_abbreviations_do_not_end_sentences(text: str) -> None:
    assert len(split_sentences(text)) == 1


def test_headings_keep_their_numbers_and_are_marked() -> None:
    segs = split_sentences(
        "Article 2. Term\nThe period of performance is one year.\n1. Purpose and Scope\nText here."
    )
    assert [(s.text, s.heading) for s in segs] == [
        ("Article 2. Term", True),
        ("The period of performance is one year.", False),
        ("1. Purpose and Scope", True),
        ("Text here.", False),
    ]


def test_numbered_clauses_and_table_rows_split() -> None:
    assert texts("5.1 First clause\n5.2 Second clause.") == [
        "5.1 First clause",
        "5.2 Second clause.",
    ]
    assert texts("Personnel: $62,000\nDomestic travel: $8,000") == [
        "Personnel: $62,000",
        "Domestic travel: $8,000",
    ]


def test_typed_rules_one_per_line_without_periods() -> None:
    assert texts("No alcohol\nMeals up to $75\nNever buy from Amazon.") == [
        "No alcohol",
        "Meals up to $75",
        "Never buy from Amazon.",
    ]


@pytest.mark.parametrize("pdf", ["grants/demo_grant.pdf", "policies/northwind_te_policy.pdf"])
def test_sample_documents_have_no_broken_fragments(pdf: str) -> None:
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages((FIXTURES / pdf).read_bytes())}
    for text in pages.values():
        for seg in split_sentences(text):
            assert text[seg.start : seg.end] == seg.text  # exact offsets for citations
            if not seg.heading and "$" not in seg.text:
                assert seg.text[-1] in ".;:)", seg.text
