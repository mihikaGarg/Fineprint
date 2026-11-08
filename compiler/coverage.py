"""Coverage report: what happened to every clause in the document.

Each clause (sentence) is classified as:
- rule: a verified rule cites it;
- flagged: the model said it might affect spending but is ambiguous;
- rejected: a rule was proposed from it but failed verification or parsing;
- no_rule: nothing was found in it.
So a reviewer can see that the whole document was read, not just what was found.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel

from compiler.propose import SENTENCE_SPLIT_RE
from contracts.models import Ruleset

ClauseStatus = Literal["rule", "flagged", "rejected", "no_rule"]
MIN_WORDS = 3  # skip headings like "Article 3."


class Clause(BaseModel):
    page: int
    char_start: int
    char_end: int
    text: str
    status: ClauseStatus
    detail: str = ""


class Coverage(BaseModel):
    total: int
    rules: int
    flagged: int
    rejected: int
    no_rule: int
    clauses: list[Clause]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _clauses(page_text: str) -> list[tuple[int, int, str]]:
    """Sentence spans as (start, end, text), with exact offsets into the page."""
    out: list[tuple[int, int, str]] = []
    pos = 0
    for part in SENTENCE_SPLIT_RE.split(page_text):
        text = part.strip()
        if not text:
            continue
        start = page_text.find(text, pos)
        if start == -1:
            continue
        end = start + len(text)
        pos = end
        if len(text.split()) >= MIN_WORDS:
            out.append((start, end, text))
    return out


def _overlap(spans: list[tuple[int, int, int, str]], page: int, start: int, end: int) -> str | None:
    for p, s, e, detail in spans:
        if p == page and s < end and start < e:
            return detail
    return None


def build_coverage(
    pages: dict[int, str],
    ruleset: Ruleset,
    rejected: list[dict[str, Any]],
    flagged: list[dict[str, Any]],
) -> Coverage:
    rule_spans = [
        (r.citation.page, r.citation.char_start, r.citation.char_end, r.name) for r in ruleset.rules
    ]
    flag_spans = [(f["page"], f["char_start"], f["char_end"], f["why"]) for f in flagged]
    rejected_quotes = [
        (
            x.get("candidate", {}).get("page"),
            _norm(str(x.get("candidate", {}).get("quote", ""))),
            x.get("reason", ""),
        )
        for x in rejected
    ]

    clauses: list[Clause] = []
    for page, text in sorted(pages.items()):
        for start, end, clause_text in _clauses(text):
            status: ClauseStatus = "no_rule"
            detail = ""
            if (d := _overlap(rule_spans, page, start, end)) is not None:
                status, detail = "rule", d
            elif (d := _overlap(flag_spans, page, start, end)) is not None:
                status, detail = "flagged", d
            else:
                norm = _norm(clause_text)
                for p, q, reason in rejected_quotes:
                    if q and p == page and (q in norm or norm in q):
                        status, detail = "rejected", str(reason)
                        break
            clauses.append(
                Clause(
                    page=page,
                    char_start=start,
                    char_end=end,
                    text=clause_text,
                    status=status,
                    detail=detail,
                )
            )

    counts = {
        s: sum(c.status == s for c in clauses) for s in ("rule", "flagged", "rejected", "no_rule")
    }
    return Coverage(
        total=len(clauses),
        rules=counts["rule"],
        flagged=counts["flagged"],
        rejected=counts["rejected"],
        no_rule=counts["no_rule"],
        clauses=clauses,
    )
