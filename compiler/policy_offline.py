"""Offline policy reader: no API key, no network.

Recognises common phrasings ("No alcohol", "Meals up to $75", "Over $5,000
needs the finance director", "Never buy from Amazon", "Receipts over $25")
and proposes rule items in the same shape Claude returns. They then go through
exactly the same validation as Claude's output (verbatim quote, amounts parsed
by code, enum checks, multiple-choice questions for anything missing).

It is far less flexible than Claude; sentences it doesn't recognise are listed
as not understood rather than guessed.
"""

import re
from typing import Any

from compiler.propose import SENTENCE_SPLIT_RE

CATEGORY_WORDS: dict[str, tuple[str, ...]] = {
    "alcohol": ("alcohol", "wine", "beer", "liquor", "drinks", "bar tab"),
    "first_class_airfare": ("first class", "first-class"),
    "meals": ("meal", "lunch", "dinner", "breakfast", "food"),
    "lodging": ("hotel", "lodging", "airbnb"),
    "entertainment": ("entertainment", "concert", "tickets", "sporting"),
    "gifts": ("gift",),
    "software": ("software", "subscription", "saas"),
    "equipment": ("equipment", "laptop", "computer", "hardware", "monitor"),
    "supplies": ("supplies", "stationery"),
    "airfare": ("airfare", "flight", "airline"),
    "ground_transport": ("taxi", "uber", "lyft", "rideshare", "car service"),
    "travel_domestic": ("travel", "train", "conference registration"),
    "lobbying": ("lobbying",),
    "fundraising": ("fundraising",),
}
NEGATIONS = (
    "no ",
    "never",
    "not allowed",
    "not permitted",
    "not reimbursable",
    "not eligible",
    "prohibited",
    "unallowable",
    "cannot",
    "can't",
    "don't",
    "do not",
    "banned",
)
NEGATION_RE = re.compile(r"\b(?:" + "|".join(re.escape(n.strip()) for n in NEGATIONS) + r")\b")
EXCEPT_SPLIT_RE = re.compile(r"\b(?:except|unless|other than)\b")
CAP_RE = re.compile(
    r"\b(up to|max(?:imum)?(?: of)?|no more than|at most|capped at|limit(?:ed)? to|under)\s+\$"
)
MERCHANT_RE = re.compile(
    r"\b(?:never|don't|do not|no)\s+(?:buy|purchase|shop|order)(?:ing|s)?\s+"
    r"(?:anything\s+)?(?:from|at)\s+(.+?)[.;!]?$",
    re.IGNORECASE,
)
ROLE_RE = re.compile(
    r"(?:approval from|approved by|sign-?off from|needs|requires|require|need)\s+"
    r"(?:the\s+|a\s+|an\s+|your\s+|our\s+)?([a-z][a-z ]{1,30}?)(?:'s)?"
    r"(?:\s+approval|\s+to approve|\s+sign-?off|\s+before|[.;!]|$)"
)
NON_ROLES = {"receipt", "receipts", "approval", "a receipt"}


def _categories(lower: str) -> list[str]:
    cats = [cat for cat, words in CATEGORY_WORDS.items() if any(w in lower for w in words)]
    if "first_class_airfare" in cats:  # "first class flights" is not all airfare
        cats = [c for c in cats if c not in ("airfare", "travel_domestic")]
    return cats


def _item(rule_type: str, quote: str, **kw: Any) -> dict[str, Any]:
    return {
        "rule_type": rule_type,
        "page": kw.get("page", 1),
        "quote": quote,
        "categories": kw.get("categories", []),
        "action": kw.get("action", "unspecified"),
        "approver_role": kw.get("approver_role", ""),
        "merchants": kw.get("merchants", []),
        "questions": [],
    }


def read_policy(pages: dict[int, str] | str) -> dict[str, Any]:
    if isinstance(pages, str):
        pages = {1: pages}
    rules: list[dict[str, Any]] = []
    not_rules: list[dict[str, str]] = []
    for page, text in sorted(pages.items()):
        _read_page(page, text, rules, not_rules)
    return {"rules": rules, "not_rules": not_rules}


def _read_page(
    page: int, text: str, rules: list[dict[str, Any]], not_rules: list[dict[str, str]]
) -> None:
    for raw in SENTENCE_SPLIT_RE.split(text):
        sentence = raw.strip()
        if not sentence:
            continue
        lower = sentence.lower()
        # Categories come from the rule itself, not its exception
        # ("No alcohol except at client entertainment events" bans alcohol only).
        main = EXCEPT_SPLIT_RE.split(lower, maxsplit=1)[0]
        has_amount = "$" in sentence

        if m := MERCHANT_RE.search(sentence):
            merchants = [x.strip() for x in re.split(r",|\bor\b|\band\b", m.group(1)) if x.strip()]
            rules.append(_item("merchant_restriction", sentence, page=page, merchants=merchants))
        elif "receipt" in lower:
            rules.append(
                _item("receipt_required", sentence, page=page, categories=_categories(lower))
            )
        elif (
            (role := ROLE_RE.search(lower))
            and role.group(1).strip() not in NON_ROLES
            and (has_amount or "approv" in lower)
        ):
            role_text = re.sub(
                r"^(?:approval|sign-?off)\s+(?:from|by)\s+(?:the\s+|a\s+|an\s+|your\s+|our\s+)?",
                "",
                role.group(1).strip(),
            )
            slug = re.sub(r"\s+", "_", role_text)
            rules.append(
                _item(
                    "approval_required",
                    sentence,
                    page=page,
                    approver_role=slug,
                    categories=_categories(main),
                )
            )
        elif has_amount and CAP_RE.search(lower):
            rules.append(_item("per_item_cap", sentence, page=page, categories=_categories(main)))
        elif NEGATION_RE.search(main) and _categories(main):
            rules.append(
                _item("category_prohibition", sentence, page=page, categories=_categories(main))
            )
        else:
            not_rules.append(
                {"quote": sentence, "why": "Not recognised as a spending rule (offline reader)"}
            )
