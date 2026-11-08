"""Policy assistant: turn a company's plain-English expense rules into rules.

Flow:
1. The user writes their rules ("No alcohol. Meals up to $75. Anything over
   $5k needs the finance director.").
2. Claude splits the text into rules: for each, the rule type, the user's
   sentence copied verbatim, and its reading of categories, action and
   approver. Where it isn't sure, it proposes a multiple-choice question.
3. Code takes over: the quote must appear verbatim in the user's text, dollar
   amounts are parsed from the quote (never from the model), every enum value
   is validated, and any required field still missing becomes a question.
4. The user answers questions with one tap; answers are validated against the
   offered options and recorded on the rule as part of its source.

Rules come out `proposed` and are only enforced after a person approves them.
"""

import hashlib
import re
from typing import Any, cast

from pydantic import BaseModel, Field

from compiler.citation import verify_citation
from compiler.propose import parse_dollars_to_cents
from contracts.models import KNOWN_CATEGORIES, Ruleset, SpendRule
from shared.llm import Effort, LLMError, LLMRequest, Transport, anthropic_transport, complete_json

POLICY_RULE_TYPES = (
    "category_prohibition",
    "per_item_cap",
    "approval_required",
    "merchant_restriction",
    "receipt_required",
)
ACTIONS = ("block", "review")
ROLE_RE = re.compile(r"^[a-z][a-z_]{1,39}$")
PERIOD_LIMIT_RE = re.compile(
    r"\bper (day|night|trip|week|month|year)\b|\b(daily|weekly|monthly|annual)\b"
)

RULE_NAMES = {
    "category_prohibition": "Not allowed",
    "per_item_cap": "Spending cap",
    "approval_required": "Approval required",
    "merchant_restriction": "Restricted merchant",
    "receipt_required": "Receipt required",
}

FIELD_LABELS = {"action": "What should happen?", "categories": "Which kind of expense?"}
ACTION_OPTIONS = [
    {"label": "Block it", "value": "block"},
    {"label": "Allow but send for review", "value": "review"},
]


class Option(BaseModel):
    label: str
    value: str


class Question(BaseModel):
    id: str
    rule_id: str
    field: str
    question: str
    options: list[Option]


class PolicyDraft(BaseModel):
    draft_id: str
    name: str
    text: str
    drafter: str = "llm"  # "llm" or "offline ..." (which reader produced the rules)
    ruleset: Ruleset
    questions: list[Question] = Field(default_factory=list[Question])
    rejected: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    not_rules: list[dict[str, str]] = Field(default_factory=list[dict[str, str]])


SYSTEM_PROMPT = f"""\
You help a company set up its expense policy. The user writes their rules in \
plain English. Split the text into individual rules. You do not decide whether \
any expense is allowed; code does that.

Rule types:
- category_prohibition: a kind of expense is never allowed ("No alcohol").
- per_item_cap: a single expense in some categories may not exceed an amount \
("Meals up to $75"). Only per-item caps are supported; if the user means per \
day, per trip or per month, still report it and the system will flag it.
- approval_required: expenses at or above an amount need approval from a role \
("Anything over $5,000 needs the finance director").
- merchant_restriction: purchases from named merchants are not allowed.
- receipt_required: expenses at or above an amount need a receipt.

For each rule:
- "quote": copy the user's sentence or clause character for character. Do not \
paraphrase. Include the amount if there is one.
- "categories": which of these categories it applies to, or [] for all: \
{", ".join(KNOWN_CATEGORIES)}.
- "action": "block" or "review" if the user said what should happen when the \
rule is broken, otherwise "unspecified".
- "approver_role": for approval_required, the role in snake_case \
(e.g. "finance_director"), otherwise "".
- "merchants": for merchant_restriction, merchant names exactly as written.
- "questions": a multiple-choice question for anything you are unsure about \
(field "action", "categories" or "approver_role"), with 2 to 4 short options. \
Each option's value must be a valid value for that field.

Put sentences that are not expense rules in "not_rules" with a short reason. \
Never invent rules the user did not write."""

POLICY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_type": {"type": "string", "enum": list(POLICY_RULE_TYPES)},
                    "quote": {"type": "string"},
                    "categories": {
                        "type": "array",
                        "items": {"type": "string", "enum": list(KNOWN_CATEGORIES)},
                    },
                    "action": {"type": "string", "enum": ["block", "review", "unspecified"]},
                    "approver_role": {"type": "string"},
                    "merchants": {"type": "array", "items": {"type": "string"}},
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {
                                    "type": "string",
                                    "enum": ["action", "categories", "approver_role"],
                                },
                                "question": {"type": "string"},
                                "options": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "label": {"type": "string"},
                                            "value": {"type": "string"},
                                        },
                                        "required": ["label", "value"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["field", "question", "options"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "rule_type",
                    "quote",
                    "categories",
                    "action",
                    "approver_role",
                    "merchants",
                    "questions",
                ],
                "additionalProperties": False,
            },
        },
        "not_rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"quote": {"type": "string"}, "why": {"type": "string"}},
                "required": ["quote", "why"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["rules", "not_rules"],
    "additionalProperties": False,
}


def _valid_value(field: str, value: str) -> bool:
    if field == "action":
        return value in ACTIONS
    if field == "categories":
        return value in KNOWN_CATEGORIES
    if field == "approver_role":
        return bool(ROLE_RE.match(value))
    return False


def _clean_questions(raw: list[dict[str, Any]], rule_id: str) -> dict[str, Question]:
    """Keep only questions whose options are all valid values for their field."""
    out: dict[str, Question] = {}
    for q in raw:
        field = str(q.get("field", ""))
        options = [
            Option(label=str(o.get("label", "")).strip(), value=str(o.get("value", "")))
            for o in q.get("options", [])
        ]
        options = [o for o in options if o.label and _valid_value(field, o.value)]
        if field in out or len(options) < 2:
            continue
        out[field] = Question(
            id=f"{rule_id}:{field}",
            rule_id=rule_id,
            field=field,
            question=str(q.get("question", "")).strip() or FIELD_LABELS.get(field, field),
            options=options[:4],
        )
    return out


def _build_rule(
    item: dict[str, Any], rule_id: str, text: str
) -> tuple[SpendRule, list[Question]] | str:
    """Validate one model-proposed rule. Returns (rule, open questions) or a rejection reason."""
    rule_type = str(item.get("rule_type", ""))
    quote = str(item.get("quote", "")).strip()
    if rule_type not in POLICY_RULE_TYPES:
        return f"Unsupported rule type '{rule_type}'"
    citation = verify_citation({1: text}, page_number=1, candidate_quote=quote)
    if citation is None:
        return "Quote is not in the policy text"
    quote, lower = citation.quote, citation.quote.lower()

    categories = [c for c in item.get("categories", []) if c in KNOWN_CATEGORIES]
    action = item.get("action") if item.get("action") in ACTIONS else None
    questions = _clean_questions(item.get("questions", []), rule_id)
    params: dict[str, Any] = {"clarifications": []}

    if rule_type == "category_prohibition":
        if not categories and "categories" not in questions:
            return "Couldn't match this to a known cost category"
        params["prohibited_categories"] = categories
        questions.pop("action", None)  # prohibitions always block

    elif rule_type == "per_item_cap":
        cap = parse_dollars_to_cents(quote)
        if cap is None:
            return "No dollar amount in this rule"
        if PERIOD_LIMIT_RE.search(lower):
            return "Per-day, per-trip and other period limits aren't supported yet"
        params.update(cap_cents=cap, categories=categories, action=action)

    elif rule_type == "approval_required":
        role = str(item.get("approver_role", ""))
        if not ROLE_RE.match(role) and "approver_role" not in questions:
            return "No approver named"
        params.update(
            threshold_cents=parse_dollars_to_cents(quote) or 0,
            approver_role=role if ROLE_RE.match(role) else None,
            categories=categories,
            action=action,
        )

    elif rule_type == "merchant_restriction":
        merchants = [
            str(m).strip()
            for m in item.get("merchants", [])
            if len(str(m).strip()) >= 2 and str(m).strip().lower() in lower
        ]
        if not merchants:
            return "No merchant name found in the rule"
        params["merchants"] = merchants
        questions.pop("action", None)

    elif rule_type == "receipt_required":
        params.update(threshold_cents=parse_dollars_to_cents(quote) or 0, categories=categories)
        questions.pop("action", None)

    # Every required field must have a value or an open question.
    if rule_type in ("per_item_cap", "approval_required") and action is None:
        questions.setdefault(
            "action",
            Question(
                id=f"{rule_id}:action",
                rule_id=rule_id,
                field="action",
                question=f'"{quote}": what should happen when this is broken?',
                options=[Option(**o) for o in ACTION_OPTIONS],
            ),
        )
    # Drop questions for fields that already have a value.
    if params.get("approver_role"):
        questions.pop("approver_role", None)
    if rule_type != "category_prohibition" and categories:
        questions.pop("categories", None)
    if rule_type == "category_prohibition" and categories:
        questions.pop("categories", None)

    rule = SpendRule(
        id=rule_id,
        name=RULE_NAMES[rule_type],
        rule_type=rule_type,
        citation=citation,
        params=params,
        source="policy",
        status="proposed",
    )
    return rule, list(questions.values())


def draft_policy(
    text: str,
    name: str = "Company expense policy",
    transport: Transport = anthropic_transport,
    effort: Effort = "medium",
) -> PolicyDraft:
    """Turn plain-English policy text into proposed rules plus open questions, using Claude."""
    text = text.strip()
    if not text:
        raise ValueError("Policy text is empty")
    request = LLMRequest(system=SYSTEM_PROMPT, prompt=text, schema=POLICY_SCHEMA, effort=effort)
    data: Any = complete_json(request, transport=transport)
    if not isinstance(data, dict):
        raise LLMError("Model output did not match the policy schema")
    parsed: dict[str, Any] = cast(dict[str, Any], data)
    if not isinstance(parsed.get("rules"), list):
        raise LLMError("Model output did not match the policy schema")
    return draft_from_items(text, name, parsed, drafter="llm")


def draft_from_items(text: str, name: str, data: dict[str, Any], drafter: str) -> PolicyDraft:
    """Validate proposed rule items (from Claude or the offline reader) into a draft."""
    items: list[dict[str, Any]] = data.get("rules", [])
    not_rules: list[dict[str, Any]] = data.get("not_rules", [])
    draft_id = "policy_" + hashlib.sha256(text.encode()).hexdigest()[:12]
    rules: list[SpendRule] = []
    questions: list[Question] = []
    rejected: list[dict[str, Any]] = []
    for item in items:
        built = _build_rule(item, f"{draft_id}_{len(rules) + 1:02d}", text)
        if isinstance(built, str):
            rejected.append({"candidate": item, "reason": built})
            continue
        rule, open_qs = built
        rules.append(rule)
        questions.extend(open_qs)

    return PolicyDraft(
        draft_id=draft_id,
        name=name,
        text=text,
        drafter=drafter,
        ruleset=Ruleset(grant_id=draft_id, grant_name=name, rules=rules),
        questions=questions,
        rejected=rejected,
        not_rules=[
            {"quote": str(n.get("quote", "")), "why": str(n.get("why", ""))} for n in not_rules
        ],
    )


class AnswerError(ValueError):
    pass


def apply_answers(draft: PolicyDraft, answers: dict[str, str]) -> PolicyDraft:
    """Apply one-tap answers. Each answer must be one of the question's options."""
    by_id = {q.id: q for q in draft.questions}
    rules = {r.id: r.model_copy(deep=True) for r in draft.ruleset.rules}
    for qid, value in answers.items():
        q = by_id.get(qid)
        if q is None:
            raise AnswerError(f"Unknown question '{qid}'")
        option = next((o for o in q.options if o.value == value), None)
        if option is None:
            raise AnswerError(f"'{value}' is not an option for question '{qid}'")
        rule = rules[q.rule_id]
        if q.field == "categories":
            key = (
                "prohibited_categories"
                if rule.rule_type == "category_prohibition"
                else "categories"
            )
            rule.params[key] = [value]
        else:
            rule.params[q.field] = value
        rule.params["clarifications"].append({"question": q.question, "answer": option.label})

    return draft.model_copy(
        update={
            "ruleset": draft.ruleset.model_copy(
                update={"rules": [rules[r.id] for r in draft.ruleset.rules]}
            ),
            "questions": [q for q in draft.questions if q.id not in answers],
        }
    )


def open_question_rule_ids(draft: PolicyDraft) -> set[str]:
    return {q.rule_id for q in draft.questions}
