"""Spot rules that are narrower than the categories we can check.

Rules are enforced per category (meals, domestic travel, equipment...). A
sentence like "Spousal travel is not reimbursable" or "Laptops cost no more than
$2,000" talks about something smaller than its category; enforcing it on the
whole category would block or flag far more than the policy says. When that's
the case we return the narrower phrase so the rule can be confirmed by a person
instead of silently applied to everything.

This runs in code on every proposed rule, whether it came from Claude or the
offline reader.
"""

import re

from compiler.policy_offline import CATEGORY_WORDS

# Words that name something smaller than their category ("wine" is not all alcohol).
ITEM_WORDS = {
    "laptop",
    "computer",
    "monitor",
    "uber",
    "lyft",
    "wine",
    "beer",
    "liquor",
    "drinks",
    "bar tab",
    "concert",
    "tickets",
    "sporting",
    "airbnb",
    "train",
    "car service",
    "conference registration",
    "stationery",
    "breakfast",
    "lunch",
    "dinner",
}
# Words that sit next to a category word without narrowing it.
NEUTRAL = {
    # grammar and rule verbs
    "is", "are", "was", "be", "may", "must", "will", "shall", "should", "can", "cannot", "not",
    "no", "never", "do", "don't", "book", "buy", "purchase", "charged", "charge", "reimbursed",
    "reimbursable", "allowed", "permitted", "prohibited", "banned", "unallowable", "require",
    "requires", "required", "need", "needs", "needed", "up", "over", "above", "under",
    "exceeding", "exceed", "more", "less", "than", "to", "only", "per", "at", "in", "on", "for",
    "of", "from", "with", "and", "or", "the", "a", "an", "any", "all", "every", "each", "our",
    "your", "their", "cost", "costs", "spend", "spent", "limited", "capped", "maximum",
    # generic nouns and modifiers that don't narrow a category
    "expense", "expenses", "charges", "item", "items", "spending", "purchases", "fees", "fee",
    "fares", "fare", "rates", "rate", "business", "domestic", "work", "company", "employee",
    "employees", "staff", "official", "subscription", "subscriptions", "beverages", "beverage",
}  # fmt: skip
# Subjects that mean "any expense" for rules with no category.
GENERIC_SUBJECT = {
    "expenses", "expense", "purchases", "purchase", "anything", "all", "any", "every", "each",
    "costs", "cost", "spend", "spending", "charges", "charge", "items", "item", "single",
    "individual", "employee", "employees", "staff", "the", "a", "an", "of", "for", "our", "your",
}  # fmt: skip
AMOUNT_START_RE = re.compile(r"\b(over|above|exceeding|under|of|more than|up to)\b|\$")
EXCEPT_RE = re.compile(r"\b(except|unless|other than)\b")
WORD_RE = re.compile(r"[a-z][a-z'-]*")
ALL_KEYWORDS = {w for words in CATEGORY_WORDS.values() for w in words}


def _is_keyword(word: str) -> bool:
    return any(word == k or word.rstrip("s") == k or word.startswith(k) for k in ALL_KEYWORDS)


def _neighbour_modifiers(main: str, keyword: str) -> list[str]:
    """Words right before/after the keyword that aren't neutral or other category words."""
    out: list[str] = []
    for match in re.finditer(re.escape(keyword) + r"[a-z]*", main):
        before = WORD_RE.findall(main[: match.start()])
        after = WORD_RE.findall(main[match.end() :])
        for word in ([before[-1]] if before else []) + ([after[0]] if after else []):
            if word not in NEUTRAL and not _is_keyword(word):
                out.append(word)
    return out


def narrower_scope(quote: str, rule_type: str, categories: list[str]) -> str | None:
    """The narrower thing a rule is really about, or None if the category fits."""
    if rule_type in ("merchant_restriction", "receipt_required"):
        return None
    main = EXCEPT_RE.split(quote.lower(), maxsplit=1)[0]

    # "Purchases from Amazon require procurement approval": a merchant condition.
    if m := re.search(r"\bfrom ([A-Z][\w&.'-]*(?: [A-Z][\w&.'-]*)*)", quote):
        return f"purchases from {m.group(1)}"

    if not categories:
        subject = WORD_RE.findall(AMOUNT_START_RE.split(main, maxsplit=1)[0])
        specific = [w for w in subject if w not in GENERIC_SUBJECT and w not in NEUTRAL]
        return " ".join(subject) if specific else None

    for category in categories:
        for keyword in sorted(CATEGORY_WORDS.get(category, ()), key=len, reverse=True):
            if keyword not in main:
                continue
            modifiers = _neighbour_modifiers(main, keyword)
            if keyword in ITEM_WORDS or modifiers:
                found = re.search(
                    r"(?:[a-z'-]+ )?" + re.escape(keyword) + r"[a-z]*(?: [a-z'-]+)?", main
                )
                phrase = found.group(0) if found else keyword
                words = [w for w in phrase.split() if w not in NEUTRAL or _is_keyword(w)]
                return " ".join(words) or keyword
            break  # the longest keyword for this category matched cleanly
    return None
