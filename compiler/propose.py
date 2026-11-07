"""Deterministic rule proposer.

Finds candidate clauses by keyword and derives every rule parameter from the
clause text itself (dates, dollar thresholds, categories). If a parameter can't
be parsed from the quote, the candidate is rejected rather than filled with a
default. An LLM-backed proposer (via shared/llm.py) can replace the keyword
search later; the parsing and verification steps stay the same.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

MONTHS = {
    m: i
    for i, m in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        start=1,
    )
}
DATE_RE = re.compile(
    r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),\s*(\d{4})\b",
    re.IGNORECASE,
)
DOLLAR_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;])\s+")

PROHIBITED_KEYWORDS = {
    "alcohol": "alcohol",
    "entertainment": "entertainment",
    "lobbying": "lobbying",
    "fundraising": "fundraising",
}
BUDGET_LINE_KEYWORDS = {
    "domestic travel": ("travel_domestic", "Travel budget line"),
    "foreign travel": ("travel_foreign", "Foreign travel budget line"),
    "equipment expenditures": ("equipment", "Equipment budget line"),
}


@dataclass
class Candidate:
    name: str
    rule_type: str
    page: int
    quote: str
    params: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class Proposal:
    candidates: list[Candidate] = field(default_factory=list[Candidate])
    rejected: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


def parse_dates(text: str) -> list[date]:
    return [date(int(y), MONTHS[m.lower()], int(d)) for m, d, y in DATE_RE.findall(text)]


def parse_dollars_to_cents(text: str) -> int | None:
    """First dollar amount in text as integer cents, parsed without floats."""
    match = DOLLAR_RE.search(text)
    if not match:
        return None
    whole, frac = match.groups()
    return int(whole.replace(",", "")) * 100 + int(frac or "0")


def _sentences(text: str) -> list[str]:
    """Sentences as exact substrings of the page text (so citations verify)."""
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def propose_rules(pages: dict[int, str]) -> Proposal:
    out = Proposal()

    def reject(page: int, quote: str, rule_type: str, reason: str) -> None:
        out.rejected.append(
            {"candidate": {"page": page, "quote": quote, "rule_type": rule_type}, "reason": reason}
        )

    for page, text in sorted(pages.items()):
        for sentence in _sentences(text):
            lower = sentence.lower()

            if "period of performance" in lower:
                dates = parse_dates(sentence)
                if len(dates) >= 2 and dates[0] <= dates[1]:
                    start, end = dates[0], dates[1]
                    out.candidates.append(
                        Candidate(
                            "Period of performance",
                            "period_of_performance",
                            page,
                            sentence,
                            {
                                "start_date": start.isoformat(),
                                "end_date": end.isoformat(),
                                "label": f"{start:%b} {start.day}, {start.year} to "
                                f"{end:%b} {end.day}, {end.year}",
                            },
                        )
                    )
                else:
                    reject(page, sentence, "period_of_performance", "No start and end date found")

            if "unallowable" in lower:
                categories = [c for k, c in PROHIBITED_KEYWORDS.items() if k in lower]
                if categories:
                    out.candidates.append(
                        Candidate(
                            "Category prohibition",
                            "category_prohibition",
                            page,
                            sentence,
                            {"prohibited_categories": categories},
                        )
                    )

            if "budget" in lower:
                for keyword, (line, name) in BUDGET_LINE_KEYWORDS.items():
                    if keyword in lower:
                        out.candidates.append(
                            Candidate(
                                name,
                                "budget_limit",
                                page,
                                sentence,
                                {"budget_line": line},
                            )
                        )

            if "prior written approval" in lower or "prior approval" in lower:
                cents = parse_dollars_to_cents(sentence)
                if cents is None:
                    reject(page, sentence, "threshold_approval", "No dollar threshold in clause")
                elif "equipment" not in lower:
                    reject(page, sentence, "threshold_approval", "Clause names no cost category")
                else:
                    out.candidates.append(
                        Candidate(
                            "Equipment prior approval",
                            "threshold_approval",
                            page,
                            sentence,
                            {
                                "category": "equipment",
                                "threshold_cents": cents,
                                "requirement": "prior written approval",
                            },
                        )
                    )

    return out
