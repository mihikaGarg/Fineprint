"""Policy setup chat: upload the company's policy, then close the gaps in conversation.

1. The company uploads its existing policy (PDF or text). It is read into
   proposed rules (by Claude when enabled, otherwise the offline reader), each
   citing its page.
2. `find_gaps` lists everything that still needs a human:
   - question:    a rule is missing a detail (e.g. block or review?)
   - exception:   a rule has an "unless/except" the engine can't check
   - vague:       wording like "reasonable" that can't be enforced as written
   - unsupported: a rule type not supported yet (per-night limits)
   - missing:     common topics the policy doesn't cover (receipts, approvals, alcohol)
   - conflict:    where a linked grant is stricter than the policy
3. The chat asks about one gap at a time, with multiple-choice buttons and
   free-text answers. Anything the user says that creates or changes a rule is
   written as a sentence on a "Setup conversation" page, and the rule cites
   that sentence, so every rule still traces back to verifiable text.
4. When nothing is left, the user approves the rulebook.
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from compiler.citation import verify_citation
from compiler.examples import examples_for
from compiler.policy import (
    PolicyDraft,
    _build_rule,  # pyright: ignore[reportPrivateUsage]
)
from compiler.policy_offline import CATEGORY_WORDS, read_policy
from compiler.propose import parse_dollars_to_cents
from compiler.sentences import split_sentences
from contracts.models import Ruleset, SpendRule
from enforce.rules import format_cents

GapKind = Literal[
    "question", "exception", "narrow", "vague", "unsupported", "missing", "conflict", "final"
]

EXCEPT_RE = re.compile(r"\b(except|unless|other than|without prior)\b", re.IGNORECASE)
VAGUE_RE = re.compile(
    r"\b(reasonable|appropriate|modest|customary|moderate|economical|excessive|lavish|"
    r"sensible|prudent|at the discretion)\b",
    re.IGNORECASE,
)
SUGGESTED_CAPS: dict[str, tuple[int, int, int]] = {
    "meals": (5_000, 7_500, 10_000),
    "lodging": (20_000, 30_000, 40_000),
    "entertainment": (10_000, 25_000, 50_000),
    "gifts": (2_500, 5_000, 10_000),
    "ground_transport": (5_000, 10_000, 15_000),
    "airfare": (50_000, 100_000, 200_000),
}
DEFAULT_CAPS = (10_000, 25_000, 50_000)
LABELS = {
    "travel_domestic": "domestic travel",
    "travel_foreign": "foreign travel",
    "first_class_airfare": "first-class airfare",
    "ground_transport": "taxi/rideshare",
}


def label(category: str) -> str:
    return LABELS.get(category, category.replace("_", " "))


def role_label(role: str) -> str:
    """finance_director -> finance director; cfo -> CFO; it -> IT."""
    return role.upper() if len(role) <= 3 else role.replace("_", " ")


GROUP_NOUNS = {
    "approval_required": ("approval rules", "when someone spends without the required approval"),
    "per_item_cap": ("spending limits", "when someone goes over them"),
}
GROUP_OPTIONS = {
    "approval_required": [
        ("Don't allow it without the required approval", "block"),
        ("Allow it, but flag it until it's approved", "review"),
    ],
    "per_item_cap": [
        ("Don't allow anything over the limit", "block"),
        ("Allow it, but flag it for someone to check", "review"),
    ],
}
OUTCOME = {"block": "not allowed", "review": "flagged for review"}


class ChatOption(BaseModel):
    label: str
    value: str


class Gap(BaseModel):
    id: str
    kind: GapKind
    prompt: str
    options: list[ChatOption] = Field(default_factory=list[ChatOption])
    free_text_hint: str | None = None
    rule_id: str | None = None
    # A grouped question applies its answer to every rule listed here.
    rule_ids: list[str] = Field(default_factory=list[str])
    field: str | None = None
    page: int | None = None
    quote: str | None = None
    category: str | None = None
    # Answered automatically (e.g. already covered); not counted in "(2 of 6)".
    auto: bool = False
    # For "narrow" gaps: the held-back rule, applied to the whole category if the user agrees.
    rule: SpendRule | None = None
    resolved: bool = False


class ChatMessage(BaseModel):
    role: Literal["assistant", "user"]
    text: str
    gap_id: str | None = None
    options: list[ChatOption] = Field(default_factory=list[ChatOption])
    free_text_hint: str | None = None


class PolicySession(BaseModel):
    session_id: str
    name: str
    source: str
    drafter: str
    pages: dict[int, str]
    chat_page: int
    ruleset: Ruleset
    gaps: list[Gap]
    messages: list[ChatMessage] = Field(default_factory=list[ChatMessage])
    rejected: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    not_rules: list[dict[str, str]] = Field(default_factory=list[dict[str, str]])
    grant_ids: list[str] = Field(default_factory=list[str])
    approved: bool = False


def _scope(rule: SpendRule) -> str:
    """What a rule would cover if applied to its whole category, e.g. "domestic travel"."""
    cats: list[str] = rule.params.get("categories") or rule.params.get("prohibited_categories", [])
    what = " and ".join(label(c) for c in cats) or "expenses"
    threshold = int(rule.params.get("threshold_cents") or rule.params.get("cap_cents") or 0)
    if rule.rule_type == "approval_required" and threshold:
        return f"{what} from {format_cents(threshold)}"
    if rule.rule_type == "per_item_cap":
        return f"{what} over {format_cents(threshold)}"
    return what


def describe(rule: SpendRule) -> str:
    """One plain-English line for a rule, e.g. "Meals over $75: flagged for review"."""
    p = rule.params
    categories: list[str] = p.get("categories") or []
    cats = " and ".join(label(c) for c in categories) or "any expense"
    outcome = OUTCOME.get(p.get("action") or "", "you haven't said what happens yet")
    t = rule.rule_type
    if t == "category_prohibition":
        what = " and ".join(label(c) for c in p.get("prohibited_categories", []))
        allowed = "not allowed" if p.get("action", "block") == "block" else "only after review"
        line = f"{what}: {allowed}"
    elif t == "per_item_cap":
        line = f"{cats} over {format_cents(p['cap_cents'])}: {outcome}"
    elif t == "approval_required":
        role = role_label(str(p.get("approver_role") or "?"))
        threshold = int(p.get("threshold_cents", 0))
        when = f" from {format_cents(threshold)}" if threshold else ""
        verb = "need" if categories else "needs"
        line = f"{cats}{when} {verb} {role} approval; without it, {outcome}"
    elif t == "merchant_restriction":
        line = f"purchases from {', '.join(p['merchants'])}: not allowed"
    elif t == "receipt_required":
        threshold = int(p.get("threshold_cents", 0))
        when = f"from {format_cents(threshold)}" if threshold else "on every expense"
        line = f"receipt needed {when}" + (f" ({cats})" if categories else "")
    else:
        line = rule.name
    return line[:1].upper() + line[1:]


def example_line(rule: SpendRule) -> str:
    """A concrete example from the real engine, e.g. "$90 expense → flagged for review"."""
    for ex in examples_for(rule):
        if ex.verdict != "ALLOWED":
            outcome = "not allowed" if ex.verdict == "BLOCKED" else "flagged for review"
            return f" For example: {ex.description} → {outcome}."
    return ""


# --- Gap finding ----------------------------------------------------------------


def _categories(text: str) -> list[str]:
    lower = EXCEPT_RE.split(text.lower(), maxsplit=1)[0]
    cats = [c for c, words in CATEGORY_WORDS.items() if any(w in lower for w in words)]
    if "first_class_airfare" in cats:
        cats = [c for c in cats if c not in ("airfare", "travel_domestic")]
    return cats


def _sentences(pages: dict[int, str]) -> list[tuple[int, str]]:
    return [
        (page, s.text)
        for page, text in sorted(pages.items())
        for s in split_sentences(text)
        if not s.heading
    ]


def _cap_options(category: str | None) -> list[ChatOption]:
    caps = SUGGESTED_CAPS.get(category or "", DEFAULT_CAPS)
    return [ChatOption(label=format_cents(c), value=str(c)) for c in caps] + [
        ChatOption(label="Don't set a limit", value="skip")
    ]


def find_gaps(draft: PolicyDraft, grants: list[Ruleset]) -> list[Gap]:
    gaps: list[Gap] = []
    rules = draft.ruleset.rules
    cited = {(r.citation.page, r.citation.quote) for r in rules}
    rejected_quotes = {str(x["candidate"].get("quote", "")).strip() for x in draft.rejected}

    by_id = {r.id: r for r in rules}
    groups: dict[str, list[Any]] = {}
    for q in draft.questions:
        rule_type = by_id[q.rule_id].rule_type
        if q.field == "action" and rule_type in GROUP_NOUNS:
            groups.setdefault(rule_type, []).append(q)
            continue
        gaps.append(
            Gap(
                id=f"q:{q.id}",
                kind="question",
                prompt=q.question,
                options=[ChatOption(label=o.label, value=o.value) for o in q.options],
                rule_id=q.rule_id,
                field=q.field,
            )
        )
    for rule_type, qs in groups.items():
        noun, when = GROUP_NOUNS[rule_type]
        quotes = "\n".join(f'• "{by_id[q.rule_id].citation.quote}"' for q in qs)
        prompt = (
            f"Your {len(qs)} {noun} don't say what should happen {when}:\n{quotes}\n"
            "What should happen?"
            if len(qs) > 1
            else qs[0].question
        )
        options = (
            [ChatOption(label=lbl, value=v) for lbl, v in GROUP_OPTIONS[rule_type]]
            if len(qs) > 1
            else [ChatOption(label=o.label, value=o.value) for o in qs[0].options]
        )
        gaps.insert(
            0,
            Gap(
                id=f"group:{rule_type}:action",
                kind="question",
                prompt=prompt,
                options=options,
                rule_ids=[q.rule_id for q in qs],
                field="action",
            ),
        )

    for r in rules:
        if r.rule_type == "category_prohibition" and EXCEPT_RE.search(r.citation.quote):
            gaps.append(
                Gap(
                    id=f"exception:{r.id}",
                    kind="exception",
                    prompt=(
                        f'"{r.citation.quote}" (p. {r.citation.page}) has an exception I can\'t '
                        "check automatically (I can see the category, not whether the exception "
                        "applies). What should happen to these expenses?"
                    ),
                    options=[
                        ChatOption(
                            label="Flag each one so a person checks the exception", value="review"
                        ),
                        ChatOption(
                            label="Never allow them, even when the exception applies", value="block"
                        ),
                    ],
                    rule_id=r.id,
                    page=r.citation.page,
                    quote=r.citation.quote,
                )
            )

    for x in draft.rejected:
        if "narrow" not in x:
            continue
        held = SpendRule.model_validate(x["narrow"]["rule"])
        phrase = x["narrow"]["phrase"]
        scope = _scope(held)
        gaps.append(
            Gap(
                id=f"narrow:{held.id}",
                kind="narrow",
                prompt=(
                    f'"{held.citation.quote}" (p. {held.citation.page}) is only about {phrase}. '
                    f"I can't tell {phrase} apart from other {scope}, so I'd have to apply it to "
                    f"all {scope}. What should I do?"
                ),
                options=[
                    ChatOption(
                        label=f"Apply it to all {scope}, but flag them for review", value="review"
                    ),
                    ChatOption(label=f"Apply it to all {scope} and don't allow any", value="block"),
                    ChatOption(label=f"Skip it; someone checks {phrase} by hand", value="skip"),
                ],
                page=held.citation.page,
                quote=held.citation.quote,
                rule=held,
            )
        )

    for x in draft.rejected:
        quote = str(x["candidate"].get("quote", "")).strip()
        page = x["candidate"].get("page", 1)
        cents = parse_dollars_to_cents(quote)
        if "period limits" in str(x.get("reason", "")) and cents:
            cats = _categories(quote)
            gaps.append(
                Gap(
                    id=f"unsupported:{page}:{len(gaps)}",
                    kind="unsupported",
                    prompt=(
                        f'"{quote}" (p. {page}) is a per-night/per-trip limit, which I can\'t '
                        "check yet. Want me to check each single charge against "
                        f"{format_cents(cents)} instead?"
                    ),
                    options=[
                        ChatOption(
                            label=f"Yes, check each charge against {format_cents(cents)}",
                            value="per_charge",
                        ),
                        ChatOption(label="Skip it for now", value="skip"),
                    ],
                    page=page,
                    quote=quote,
                    category=cats[0] if cats else None,
                )
            )

    for page, sentence in _sentences({k: v for k, v in draft.pages.items()}):
        if (page, sentence) in cited or sentence in rejected_quotes:
            continue
        cats = _categories(sentence)
        if VAGUE_RE.search(sentence) and cats:
            gaps.append(
                Gap(
                    id=f"vague:{page}:{len(gaps)}",
                    kind="vague",
                    prompt=(
                        f'Your policy says "{sentence}" (p. {page}). That\'s too vague to check '
                        f"automatically. What's the most a single {label(cats[0])} charge "
                        "should be?"
                    ),
                    options=_cap_options(cats[0]),
                    free_text_hint="Or type an amount, e.g. $80",
                    page=page,
                    quote=sentence,
                    category=cats[0],
                )
            )

    types = {r.rule_type for r in rules}
    covered = {
        c
        for r in rules
        for c in r.params.get("prohibited_categories", []) + (r.params.get("categories") or [])
    }
    if "receipt_required" not in types:
        gaps.append(
            Gap(
                id="missing:receipts",
                kind="missing",
                prompt="Your policy doesn't say when receipts are required. From what amount?",
                options=[
                    ChatOption(label="$25", value="2500"),
                    ChatOption(label="$75", value="7500"),
                    ChatOption(label="Always", value="0"),
                    ChatOption(label="Not required", value="skip"),
                ],
                free_text_hint="Or type an amount",
            )
        )
    if "approval_required" not in types:
        gaps.append(
            Gap(
                id="missing:approvals",
                kind="missing",
                prompt="Your policy doesn't mention approvals. Who signs off on large expenses?",
                options=[
                    ChatOption(label="Manager from $1,000", value="manager:100000"),
                    ChatOption(label="Director from $10,000", value="director:1000000"),
                    ChatOption(label="CFO from $50,000", value="cfo:5000000"),
                    ChatOption(label="No approvals needed", value="skip"),
                ],
            )
        )
    if "alcohol" not in covered:
        gaps.append(
            Gap(
                id="missing:alcohol",
                kind="missing",
                prompt="Your policy doesn't mention alcohol. How should alcohol be handled?",
                options=[
                    ChatOption(label="Don't allow alcohol", value="block"),
                    ChatOption(label="Allow it, but flag it for review", value="review"),
                    ChatOption(label="Allow it", value="skip"),
                ],
            )
        )

    for g in grants:
        for gr in g.rules:
            if gr.rule_type == "category_prohibition":
                for cat in gr.params.get("prohibited_categories", []):
                    gaps.append(
                        Gap(
                            id=f"conflict:{g.grant_id}:{gr.id}:{cat}",
                            kind="conflict",
                            prompt=(
                                f'Heads up: "{g.grant_name}" bans {label(cat)} '
                                f"(p. {gr.citation.page}: "
                                f'"{gr.citation.quote}"). Anything charged to that grant '
                                "will follow the grant, even where your policy is looser."
                            ),
                            options=[ChatOption(label="Got it", value="ok")],
                        )
                    )
            elif gr.rule_type == "threshold_approval":
                gaps.append(
                    Gap(
                        id=f"conflict:{g.grant_id}:{gr.id}",
                        kind="conflict",
                        prompt=(
                            f'Heads up: "{g.grant_name}" needs prior written approval for '
                            f"{label(gr.params.get('category', 'expenses'))} from "
                            f"{format_cents(int(gr.params.get('threshold_cents', 0)))} "
                            f"(p. {gr.citation.page}), on top of your own approvals."
                        ),
                        options=[ChatOption(label="Got it", value="ok")],
                    )
                )
    return gaps


# --- Session ------------------------------------------------------------------


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _summary(s: PolicySession, draft: PolicyDraft) -> str:
    n_pages = len(draft.pages)
    counts: dict[str, int] = {}
    for g in s.gaps:
        counts[g.kind] = counts.get(g.kind, 0) + 1
    parts = [_plural(len(s.ruleset.rules), "rule", "rules")]
    phrases = {
        "question": ("needs a detail", "need a detail"),
        "exception": ("has an exception", "have exceptions"),
        "narrow": ("is narrower than I can check", "are narrower than I can check"),
        "vague": ("is too vague to enforce", "are too vague to enforce"),
        "unsupported": ("isn't supported yet", "aren't supported yet"),
    }
    for kind, (one, many) in phrases.items():
        if n := counts.get(kind, 0):
            parts.append(f"{n} {one if n == 1 else many}")
    if n := counts.get("missing", 0):
        parts.append(_plural(n, "common topic missing", "common topics missing"))
    if n := counts.get("conflict", 0):
        parts.append(_plural(n, "note about your grant", "notes about your grant"))
    open_gaps = len(s.gaps)
    return (
        f"I read {s.source} ({_plural(n_pages, 'page', 'pages')}). Found "
        + ", ".join(parts)
        + "."
        + (
            f" Let's go through the {_plural(open_gaps, 'open item', 'open items')} one at a time."
            if open_gaps
            else ""
        )
    )


def start_session(draft: PolicyDraft, source: str, grants: list[Ruleset]) -> PolicySession:
    chat_page = max(draft.pages) + 1
    pages = {**draft.pages, chat_page: "Setup conversation."}
    s = PolicySession(
        session_id=draft.draft_id,
        name=draft.name,
        source=source,
        drafter=draft.drafter,
        pages=pages,
        chat_page=chat_page,
        ruleset=draft.ruleset,
        gaps=find_gaps(draft, grants),
        rejected=draft.rejected,
        not_rules=draft.not_rules,
        grant_ids=[g.grant_id for g in grants],
    )
    s.messages.append(ChatMessage(role="assistant", text=_summary(s, draft)))
    _ask_next(s)
    return s


def _existing_cap(s: PolicySession, category: str) -> SpendRule | None:
    return next(
        (
            r
            for r in s.ruleset.rules
            if r.rule_type == "per_item_cap" and (r.params.get("categories") or []) == [category]
        ),
        None,
    )


RULE_KEYS = (
    "prohibited_categories",
    "cap_cents",
    "categories",
    "threshold_cents",
    "approver_role",
    "merchants",
)


def _duplicate_of(s: PolicySession, rule: SpendRule) -> SpendRule | None:
    """An existing rule that says the same thing (ignoring wording and action)."""
    key = {k: rule.params.get(k) for k in RULE_KEYS}
    return next(
        (
            r
            for r in s.ruleset.rules
            if r.id != rule.id
            and r.rule_type == rule.rule_type
            and {k: r.params.get(k) for k in RULE_KEYS} == key
        ),
        None,
    )


def _ask_next(s: PolicySession) -> None:
    gap = next((g for g in s.gaps if not g.resolved), None)
    # A vague limit is already settled if that category has a cap (e.g. the user just
    # chose to check "$350 per night" per charge); don't ask for a second, clashing one.
    while gap is not None and gap.kind == "vague" and gap.category:
        existing = _existing_cap(s, gap.category)
        if existing is None:
            break
        gap.resolved = True
        gap.auto = True
        s.messages.append(
            ChatMessage(
                role="assistant",
                text=(
                    f'"{gap.quote}" (p. {gap.page}) is already covered: '
                    f"{describe(existing)}. Skipping it."
                ),
            )
        )
        gap = next((g for g in s.gaps if not g.resolved), None)
    if gap is None:
        rules = "\n".join(f"• {describe(r)}" for r in s.ruleset.rules)
        gap = Gap(
            id="final",
            kind="final",
            prompt=(
                f"That's everything. Here's your rulebook ({len(s.ruleset.rules)} rules):\n"
                f"{rules}\n\n"
                "Each one is linked to your policy or to an answer you gave here. Approve it so it "
                'starts checking expenses? You can also type another rule, like "Gifts over $100 '
                "need the CEO's approval.\""
            ),
            options=[ChatOption(label="Approve all rules", value="approve")],
        )
        s.gaps.append(gap)
    # "(2 of 6)" so people know how much is left.
    counted = [g for g in s.gaps if g.kind != "final" and not g.auto]
    progress = (
        f"({sum(g.resolved for g in counted) + 1} of {len(counted)}) "
        if gap.kind != "final" and len(counted) > 1
        else ""
    )
    s.messages.append(
        ChatMessage(
            role="assistant",
            text=progress + gap.prompt,
            gap_id=gap.id,
            options=gap.options,
            free_text_hint=gap.free_text_hint or "Or type a new rule",
        )
    )


def _record(s: PolicySession, sentence: str) -> tuple[int, str]:
    """Append a sentence to the setup-conversation page; return (page, sentence)."""
    s.pages[s.chat_page] = f"{s.pages[s.chat_page]} {sentence}"
    return s.chat_page, sentence


def _add_rule(s: PolicySession, item: dict[str, Any]) -> tuple[SpendRule, list[Gap]] | str:
    built = _build_rule(item, f"{s.session_id}_{len(s.ruleset.rules) + 1:02d}", s.pages)
    if isinstance(built, str):
        return built
    rule, questions = built
    s.ruleset = s.ruleset.model_copy(update={"rules": [*s.ruleset.rules, rule]})
    new_gaps = [
        Gap(
            id=f"q:{q.id}",
            kind="question",
            prompt=q.question,
            options=[ChatOption(label=o.label, value=o.value) for o in q.options],
            rule_id=q.rule_id,
            field=q.field,
        )
        for q in questions
    ]
    return rule, new_gaps


def _update_rule(
    s: PolicySession, rule_id: str, params: dict[str, Any], note: dict[str, str]
) -> SpendRule:
    rules: list[SpendRule] = []
    updated: SpendRule | None = None
    for r in s.ruleset.rules:
        if r.id == rule_id:
            new_params = {**r.params, **params}
            new_params["clarifications"] = [*r.params.get("clarifications", []), note]
            r = r.model_copy(update={"params": new_params})
            updated = r
        rules.append(r)
    assert updated is not None
    s.ruleset = s.ruleset.model_copy(update={"rules": rules})
    return updated


def _item(rule_type: str, page: int, quote: str, **kw: Any) -> dict[str, Any]:
    return {
        "rule_type": rule_type,
        "page": page,
        "quote": quote,
        "categories": kw.get("categories", []),
        "action": kw.get("action", "unspecified"),
        "approver_role": kw.get("approver_role", ""),
        "merchants": kw.get("merchants", []),
        "questions": [],
    }


class ReplyError(ValueError):
    pass


def reply(
    s: PolicySession, gap_id: str | None, value: str | None, text: str | None
) -> PolicySession:
    """Handle one user turn: a button value for a gap, or free text."""
    s = s.model_copy(deep=True)
    gap = next((g for g in s.gaps if g.id == gap_id and not g.resolved), None) if gap_id else None
    text = (text or "").strip()

    if gap is not None and value is None and text and gap.kind in ("vague", "missing"):
        cents = parse_dollars_to_cents(text if "$" in text else f"${text}")
        if cents is not None:
            value = str(cents)

    if gap is not None and value is not None:
        option = next((o for o in gap.options if o.value == value), None)
        if option is None and not (gap.kind in ("vague", "missing") and value.isdigit()):
            raise ReplyError(f"'{value}' is not an option for this question")
        shown = option.label if option else format_cents(int(value))
        s.messages.append(ChatMessage(role="user", text=shown, gap_id=gap.id))
        confirmation = _resolve(s, gap, value, shown)
        gap.resolved = True
        s.messages.append(ChatMessage(role="assistant", text=confirmation))
        if gap.kind != "final":
            _ask_next(s)
        return s

    if not text:
        raise ReplyError("Pick an option or type something")

    # Free text: treat it as new rules in the user's own words.
    s.messages.append(ChatMessage(role="user", text=text))
    page, sentence = _record(s, text)
    found = read_policy({page: s.pages[page]})["rules"]
    found = [f for f in found if f["quote"] in sentence]
    added: list[str] = []
    new_gaps: list[Gap] = []
    duplicates: list[str] = []
    for item in found:
        result = _add_rule(s, item)
        if isinstance(result, str):
            continue
        rule, gaps = result
        if (existing := _duplicate_of(s, rule)) is not None:
            s.ruleset = s.ruleset.model_copy(
                update={"rules": [r for r in s.ruleset.rules if r.id != rule.id]}
            )
            duplicates.append(describe(existing))
            continue
        added.append(describe(rule))
        new_gaps.extend(gaps)
    if duplicates:
        s.messages.append(
            ChatMessage(role="assistant", text="You already have: " + "; ".join(duplicates) + ".")
        )
    s.gaps = [g for g in s.gaps if not (g.kind == "final" and not g.resolved)]
    if added or duplicates:
        s.approved = s.approved and not added
        insert_at = next((i for i, g in enumerate(s.gaps) if not g.resolved), len(s.gaps))
        s.gaps[insert_at:insert_at] = new_gaps
        if added:
            s.messages.append(
                ChatMessage(role="assistant", text="Added: " + "; ".join(added) + ".")
            )
    else:
        s.messages.append(
            ChatMessage(
                role="assistant",
                text=(
                    'I couldn\'t turn that into a rule. Try phrasing like "Meals up to $75", '
                    '"Over $10,000 needs the director\'s approval", "No alcohol" or '
                    '"Never buy from Amazon".'
                ),
            )
        )
    _ask_next(s)
    return s


def _resolve(s: PolicySession, gap: Gap, value: str, shown: str) -> str:
    note = {"question": gap.prompt, "answer": shown}

    if gap.kind == "question" and gap.rule_ids and gap.field:
        updated = [_update_rule(s, rid, {gap.field: value}, note) for rid in gap.rule_ids]
        if len(updated) == 1:
            return f"Got it: {describe(updated[0])}.{example_line(updated[0])}"
        lines = "\n".join(f"• {describe(r)}" for r in updated)
        return f"Got it:\n{lines}\n{example_line(updated[0]).strip()}"

    if gap.kind == "question" and gap.rule_id and gap.field:
        rule = next(r for r in s.ruleset.rules if r.id == gap.rule_id)
        key = gap.field
        new: Any = value
        if gap.field == "categories":
            key = (
                "prohibited_categories"
                if rule.rule_type == "category_prohibition"
                else "categories"
            )
            new = [value]
        updated_rule = _update_rule(s, gap.rule_id, {key: new}, note)
        return f"Got it: {describe(updated_rule)}.{example_line(updated_rule)}"

    if gap.kind == "exception" and gap.rule_id:
        updated_rule = _update_rule(s, gap.rule_id, {"action": value}, note)
        return f"Got it: {describe(updated_rule)}.{example_line(updated_rule)}"

    if gap.kind == "conflict":
        return "Noted."

    if gap.kind == "final":
        rules = [r.model_copy(update={"status": "approved"}) for r in s.ruleset.rules]
        s.ruleset = s.ruleset.model_copy(update={"rules": rules})
        s.approved = True
        return f"Approved. {len(rules)} rules are now checking every expense."

    if value == "skip":
        return "OK, skipping that."

    if gap.kind == "narrow" and gap.rule is not None:
        rule = gap.rule.model_copy(
            update={
                "id": f"{s.session_id}_{len(s.ruleset.rules) + 1:02d}",
                "params": {
                    **gap.rule.params,
                    "action": value,
                    "clarifications": [
                        *gap.rule.params.get("clarifications", []),
                        {
                            "question": (
                                f"Applies to all {_scope(gap.rule)}, not just what the policy names"
                            ),
                            "answer": shown,
                        },
                    ],
                },
            }
        )
        s.ruleset = s.ruleset.model_copy(update={"rules": [*s.ruleset.rules, rule]})
        return f"Done: {describe(rule)}.{example_line(rule)}"

    if gap.kind == "unsupported" and gap.quote and gap.page:
        result = _add_rule(
            s,
            _item(
                "per_item_cap",
                gap.page,
                gap.quote,
                categories=[gap.category] if gap.category else [],
                action="review",
            ),
        )
        if isinstance(result, str):
            # Per-night wording is rejected by the parser, so record the user's choice instead.
            cents = parse_dollars_to_cents(gap.quote) or 0
            cat = label(gap.category or "expenses")
            page, sentence = _record(
                s, f"Each {cat} charge over {format_cents(cents)} is flagged for review."
            )
            result = _add_rule(
                s,
                _item(
                    "per_item_cap",
                    page,
                    sentence,
                    categories=[gap.category] if gap.category else [],
                    action="review",
                ),
            )
        if isinstance(result, str):
            return f"I couldn't add that: {result}."
        rule, _ = result
        return f"Done: {describe(rule)}.{example_line(rule)}"

    if gap.kind == "vague" and gap.category:
        cents = int(value)
        page, sentence = _record(
            s,
            f"Each {label(gap.category)} charge over {format_cents(cents)} is flagged for review.",
        )
        result = _add_rule(
            s, _item("per_item_cap", page, sentence, categories=[gap.category], action="review")
        )
        if isinstance(result, str):
            return f"I couldn't add that: {result}."
        rule, _ = result
        _update_rule(
            s,
            rule.id,
            {},
            {"question": f'Clarifies "{gap.quote}" (p. {gap.page})', "answer": shown},
        )
        return f"Done: {describe(rule)}.{example_line(rule)}"

    if gap.id == "missing:receipts":
        cents = int(value)
        sentence = (
            "Receipts are required for every expense."
            if cents == 0
            else f"Receipts are required for any expense of {format_cents(cents)} or more."
        )
        page, sentence = _record(s, sentence)
        result = _add_rule(s, _item("receipt_required", page, sentence))
        if isinstance(result, str):
            return result
        return f"Done: {describe(result[0])}.{example_line(result[0])}"

    if gap.id == "missing:approvals":
        role, cents = value.split(":")
        page, sentence = _record(
            s, f"Expenses of {format_cents(int(cents))} or more need {role} approval."
        )
        result = _add_rule(
            s, _item("approval_required", page, sentence, approver_role=role, action="review")
        )
        if isinstance(result, str):
            return result
        return f"Done: {describe(result[0])}.{example_line(result[0])}"

    if gap.id == "missing:alcohol":
        sentence = (
            "Alcohol is not allowed."
            if value == "block"
            else "Alcohol is not allowed without review."
        )
        page, sentence = _record(s, sentence)
        result = _add_rule(
            s, _item("category_prohibition", page, sentence, categories=["alcohol"], action=value)
        )
        if isinstance(result, str):
            return result
        return f"Done: {describe(result[0])}.{example_line(result[0])}"

    return "Noted."


def verify_session_citations(s: PolicySession) -> bool:
    """Every rule's quote must still match its page exactly (used in tests)."""
    return all(
        verify_citation(s.pages, r.citation.page, r.citation.quote) is not None
        and s.pages[r.citation.page][r.citation.char_start : r.citation.char_end]
        == r.citation.quote
        for r in s.ruleset.rules
    )
