"""Rule proposal helpers and the offline keyword proposer.

`derive_params` turns a clause into rule parameters (dates, dollar thresholds,
categories) using only the clause text. If a parameter can't be parsed from the
quote, the candidate is rejected rather than filled with a default. Both the
keyword proposer here and the LLM proposer (compiler/llm_propose.py) use it.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from compiler.sentences import split_sentences

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
    # Clauses that might be rules but are ambiguous; shown to a person, never enforced.
    flagged: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


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
    """Sentences (not headings) as exact substrings of the page text, so citations verify."""
    return [s.text for s in split_sentences(text) if not s.heading]


RULE_TYPES = (
    "period_of_performance",
    "category_prohibition",
    "budget_limit",
    "threshold_approval",
)


def derive_params(rule_type: str, quote: str) -> tuple[str, dict[str, Any]] | str:
    """Parse a rule's name and parameters from its clause text alone.

    Returns (name, params), or a rejection reason. Shared by the keyword finder
    and the LLM proposer so no parameter ever comes from a model.
    """
    lower = quote.lower()

    if rule_type == "period_of_performance":
        dates = parse_dates(quote)
        if len(dates) < 2 or dates[0] > dates[1]:
            return "No start and end date found"
        start, end = dates[0], dates[1]
        return "Period of performance", {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "label": f"{start:%b} {start.day}, {start.year} to {end:%b} {end.day}, {end.year}",
        }

    if rule_type == "category_prohibition":
        categories = [c for k, c in PROHIBITED_KEYWORDS.items() if k in lower]
        if not categories:
            return "Clause names no known cost category"
        return "Category prohibition", {"prohibited_categories": categories}

    if rule_type == "budget_limit":
        for keyword, (line, name) in BUDGET_LINE_KEYWORDS.items():
            if keyword in lower:
                return name, {"budget_line": line}
        return "Clause names no known budget line"

    if rule_type == "threshold_approval":
        cents = parse_dollars_to_cents(quote)
        if cents is None:
            return "No dollar threshold in clause"
        if "equipment" not in lower:
            return "Clause names no cost category"
        return "Equipment prior approval", {
            "category": "equipment",
            "threshold_cents": cents,
            "requirement": "prior written approval",
        }

    return f"Unknown rule type '{rule_type}'"


def add_candidate(out: Proposal, rule_type: str, page: int, quote: str) -> None:
    """Derive params for a proposed clause and record it as a candidate or a rejection."""
    derived = derive_params(rule_type, quote)
    if isinstance(derived, str):
        out.rejected.append(
            {"candidate": {"page": page, "quote": quote, "rule_type": rule_type}, "reason": derived}
        )
        return
    name, params = derived
    out.candidates.append(Candidate(name, rule_type, page, quote, params))


def propose_rules(pages: dict[int, str]) -> Proposal:
    """Keyword-based proposer: deterministic, offline, used when no LLM is configured."""
    out = Proposal()
    for page, text in sorted(pages.items()):
        for sentence in _sentences(text):
            lower = sentence.lower()
            if "period of performance" in lower:
                add_candidate(out, "period_of_performance", page, sentence)
            if "unallowable" in lower and any(k in lower for k in PROHIBITED_KEYWORDS):
                add_candidate(out, "category_prohibition", page, sentence)
            if "budget" in lower and any(k in lower for k in BUDGET_LINE_KEYWORDS):
                add_candidate(out, "budget_limit", page, sentence)
            if "prior written approval" in lower or "prior approval" in lower:
                add_candidate(out, "threshold_approval", page, sentence)
    return out
