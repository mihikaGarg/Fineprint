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
    "travel_domestic": ("travel", "flight", "taxi", "uber", "lyft", "rideshare", "train"),
    "lobbying": ("lobbying",),
    "fundraising": ("fundraising",),
}
NEGATIONS = (
    "no ",
    "never",
    "not allowed",
    "prohibited",
    "unallowable",
    "cannot",
    "can't",
    "don't",
    "do not",
    "banned",
)
CAP_RE = re.compile(
    r"\b(up to|max(?:imum)?(?: of)?|no more than|at most|capped at|limit(?:ed)? to|under)\s+\$"
)
MERCHANT_RE = re.compile(
    r"\b(?:never|don't|do not|no)\s+(?:buy|purchase|shop|order)(?:ing)?\s+"
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
    if "first_class_airfare" in cats:  # "first class flights" is not all travel
        cats = [c for c in cats if c != "travel_domestic"]
    return cats


def _item(rule_type: str, quote: str, **kw: Any) -> dict[str, Any]:
    return {
        "rule_type": rule_type,
        "quote": quote,
        "categories": kw.get("categories", []),
        "action": kw.get("action", "unspecified"),
        "approver_role": kw.get("approver_role", ""),
        "merchants": kw.get("merchants", []),
        "questions": [],
    }


def read_policy(text: str) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    not_rules: list[dict[str, str]] = []
    for raw in SENTENCE_SPLIT_RE.split(text):
        sentence = raw.strip()
        if not sentence:
            continue
        lower = sentence.lower()
        has_amount = "$" in sentence

        if m := MERCHANT_RE.search(sentence):
            merchants = [x.strip() for x in re.split(r",|\bor\b|\band\b", m.group(1)) if x.strip()]
            rules.append(_item("merchant_restriction", sentence, merchants=merchants))
        elif "receipt" in lower:
            rules.append(_item("receipt_required", sentence, categories=_categories(lower)))
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
                    "approval_required", sentence, approver_role=slug, categories=_categories(lower)
                )
            )
        elif has_amount and CAP_RE.search(lower):
            rules.append(_item("per_item_cap", sentence, categories=_categories(lower)))
        elif any(n in lower for n in NEGATIONS) and _categories(lower):
            rules.append(_item("category_prohibition", sentence, categories=_categories(lower)))
        else:
            not_rules.append(
                {"quote": sentence, "why": "Not recognised as a spending rule (offline reader)"}
            )
    return {"rules": rules, "not_rules": not_rules}
