"""Read the approved budget from a grant agreement.

Looks for lines like "Domestic travel: $8,000" on pages that talk about the
budget (usually an exhibit), and turns each into a budget line with a verified
citation to that exact line, the same way rules are cited. Amounts are parsed
by code, in integer cents. Totals are skipped.
"""

import re

from pydantic import BaseModel

from compiler.citation import verify_citation
from compiler.propose import parse_dollars_to_cents
from contracts.models import RuleCitation

# Budget-table wording -> the budget line key rules and expenses use.
LINE_LABELS: dict[str, str] = {
    "domestic travel": "travel_domestic",
    "foreign travel": "travel_foreign",
    "international travel": "travel_foreign",
    "travel": "travel_domestic",
    "equipment": "equipment",
    "materials and supplies": "supplies",
    "supplies": "supplies",
    "personnel": "personnel",
    "salaries and wages": "personnel",
    "fringe benefits": "fringe",
    "participant support": "participant_support",
    "contractual": "contractual",
    "consultants": "contractual",
    "other direct costs": "other",
}
LINE_RE = re.compile(
    r"^\s*(?P<label>[A-Za-z][A-Za-z ,&/()-]{1,60}?)\s*[:.\s]+\$\s?[\d,]+(?:\.\d{2})?\s*$"
)
# A table row whose cells extract onto separate lines: "Equipment" then "$18,000".
SPLIT_ROW_RE = re.compile(
    r"^[ \t]*(?P<label>[A-Za-z][A-Za-z ,&/()-]{1,60}?)[ \t]*\r?\n"
    r"[ \t]*\$[ \t]?[\d,]+(?:\.\d{2})?[ \t]*$",
    re.MULTILINE,
)


class BudgetItem(BaseModel):
    line: str  # e.g. "travel_domestic"
    label: str  # as written, e.g. "Domestic travel"
    allocated_cents: int
    citation: RuleCitation


def _line_key(label: str) -> str | None:
    lower = label.lower().strip()
    if "total" in lower:
        return None
    # Longest matching wording wins ("domestic travel" before "travel").
    for words in sorted(LINE_LABELS, key=len, reverse=True):
        if words in lower:
            return LINE_LABELS[words]
    return None


def read_budget(pages: dict[int, str]) -> list[BudgetItem]:
    items: dict[str, BudgetItem] = {}
    for page, text in sorted(pages.items()):
        if "budget" not in text.lower():
            continue
        # Rows in page order, whether "Label: $X" on one line or split over two.
        rows: list[tuple[int, str, str]] = []
        offset = 0
        for raw in text.splitlines(keepends=True):
            if match := LINE_RE.match(raw.rstrip("\r\n")):
                rows.append((offset, match.group("label"), raw.strip()))
            offset += len(raw)
        rows += [
            (m.start(), m.group("label"), m.group(0).strip()) for m in SPLIT_ROW_RE.finditer(text)
        ]
        for _, label, quote in sorted(rows):
            key = _line_key(label)
            cents = parse_dollars_to_cents(quote)
            citation = verify_citation(pages, page, quote)
            if key is None or cents is None or citation is None or key in items:
                continue
            items[key] = BudgetItem(
                line=key, label=label.strip(), allocated_cents=cents, citation=citation
            )
    return list(items.values())
