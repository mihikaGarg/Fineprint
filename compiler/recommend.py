"""Suggest an answer to a setup question from the policy's own wording.

When a rule doesn't say what happens if it's broken ("Meals up to $75 per
person."), the rest of the document often does: "Violations of this policy may
result in denial of reimbursement", "Amounts over these limits require written
justification". We look in the rule's own sentence first, then the rest of the
policy, and fall back to what the wording implies. The suggestion is only
shown to the person answering; it never decides anything by itself.
"""

import re
from dataclasses import dataclass

from compiler.sentences import split_sentences

REJECT_RE = re.compile(
    r"\b(?:not (?:be )?reimburs\w*|non-?reimbursable|will not (?:be )?(?:paid|covered)|"
    r"denial of reimbursement|(?:be|is|are) denied|(?:be|is|are) rejected|"
    r"(?:employee|traveler|individual)s?(?:'s)? (?:is |are |will be )?(?:personally )?responsible|"
    r"personal expense|(?:may|must|shall) not exceed|(?:cannot|can't) exceed|not to exceed|"
    r"hard (?:limit|cap))",
    re.IGNORECASE,
)
REVIEW_RE = re.compile(
    r"\b(?:justif\w*|case[- ]by[- ]case|exceptions? (?:may|can|must) be (?:approved|requested|"
    r"reviewed)|(?:reviewed|considered) (?:by|on)|should not exceed|guidelines?|at the discretion)",
    re.IGNORECASE,
)
# A document-level sentence has to be about consequences, not any sentence with "reviewed".
CONSEQUENCE_RE = re.compile(
    r"\b(?:violat\w*|exceed\w*|over (?:the|these|this|a) limit|above (?:the|these|this) limit|"
    r"reimburs\w*|exceptions?|out[- ]of[- ]policy)",
    re.IGNORECASE,
)
FIRM_WORDS_RE = re.compile(r"\b(?:up to|maximum|max|no more than|limit(?:ed)? to|capped)\b", re.I)
SOFT_WORDS_RE = re.compile(r"\b(?:should|generally|typically|reasonable|customary|modest)\b", re.I)


@dataclass(frozen=True)
class Suggestion:
    value: str  # "block" or "review"
    reason: str  # plain English, shown under the question


def _short(text: str, limit: int = 110) -> str:
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _signal(text: str) -> str | None:
    if REJECT_RE.search(text):
        return "block"
    if REVIEW_RE.search(text):
        return "review"
    return None


def suggest_action(
    rule_type: str,
    quotes: list[tuple[int, str]],
    pages: dict[int, str],
    other_rules: frozenset[str] = frozenset(),
) -> Suggestion:
    """What to do when a cap is exceeded or an approval is missing.

    `quotes` are the (page, quote) of the rules the question is about;
    `other_rules` are the quotes of every other rule, which are rules in their
    own right ("Alcohol is not reimbursable..."), not statements about consequences.
    """
    for page, quote in quotes:
        if (value := _signal(quote)) is not None:
            return Suggestion(value, f'Your policy says "{_short(quote)}" (p. {page}).')

    own = {q for _, q in quotes} | other_rules
    home = {p for p, _ in quotes}
    found: list[tuple[int, int, str, str]] = []
    for page, text in pages.items():
        for seg in split_sentences(text):
            if seg.heading or seg.text in own or not CONSEQUENCE_RE.search(seg.text):
                continue
            if (value := _signal(seg.text)) is not None:
                found.append((0 if page in home else 1, page, seg.text, value))
    if found:
        _, page, text, value = min(found, key=lambda f: (f[0], f[1]))
        return Suggestion(value, f'Your policy says "{_short(text)}" (p. {page}).')

    wording = " ".join(q for _, q in quotes)
    if rule_type == "per_item_cap":
        if SOFT_WORDS_RE.search(wording) and not FIRM_WORDS_RE.search(wording):
            return Suggestion("review", "The limit is worded as a guideline, not a hard cap.")
        return Suggestion("block", "The limit is worded as a firm cap.")
    return Suggestion("block", "The policy says the approval is needed, not just preferred.")


def suggest_exception() -> Suggestion:
    return Suggestion(
        "review",
        "Only a person can tell whether the exception applies.",
    )
