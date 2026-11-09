"""Setup questions suggest an answer from the policy's wording and accept typed replies."""

from pathlib import Path

from compiler.extractor import extract_pdf_pages
from compiler.policy import draft_from_items
from compiler.policy_chat import PolicySession, reply, start_session
from compiler.policy_offline import read_policy
from compiler.recommend import suggest_action

POLICY_PDF = (
    Path(__file__).resolve().parents[2] / "fixtures" / "policies" / "northwind_te_policy.pdf"
)


def _session(pages: dict[int, str]) -> PolicySession:
    return start_session(draft_from_items(pages, "P", read_policy(pages), "offline"), "t", [])


def _open(s: PolicySession):
    return next(g for g in s.gaps if not g.resolved)


def test_rule_wording_decides_first() -> None:
    quote = "Meals may not exceed $75 per person."
    assert suggest_action("per_item_cap", [(1, quote)], {1: quote}).value == "block"
    quote = "Meals should not exceed $75; overages need a written justification."
    assert suggest_action("per_item_cap", [(1, quote)], {1: quote}).value == "review"


def test_rest_of_policy_is_used_and_cited() -> None:
    pages = {
        1: "Meals up to $75 per person.",
        2: "Expenses over these limits will be reviewed by the budget holder case-by-case.",
    }
    s = suggest_action("per_item_cap", [(1, "Meals up to $75 per person.")], pages)
    assert s.value == "review"
    assert "(p. 2)" in s.reason and "case-by-case" in s.reason


def test_unrelated_sentences_are_not_evidence() -> None:
    pages = {1: "Meals up to $75 per person.", 2: "Reports are reviewed by Finance each month."}
    s = suggest_action("per_item_cap", [(1, "Meals up to $75 per person.")], pages)
    assert s.value == "block" and s.reason == "The limit is worded as a firm cap."


def test_sample_policy_cites_its_violations_clause() -> None:
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages(POLICY_PDF.read_bytes())}
    gap = _open(_session(pages))
    assert gap.options[0].suggested and gap.options[0].value == "block"
    assert "denial of reimbursement" in gap.prompt and "(p. 5)" in gap.prompt


def test_exceptions_suggest_a_person_checks() -> None:
    s = _session({1: "Alcohol is not reimbursable except at client events."})
    gap = next(g for g in s.gaps if g.kind == "exception")
    assert gap.options[0].value == "review" and gap.options[0].suggested


def test_typed_reply_answers_the_open_question() -> None:
    s = _session({1: "Meals up to $75 per person."})
    gap = _open(s)
    s = reply(s, gap.id, None, "allow it")
    assert s.messages[-3].text == "allow it"
    assert s.messages[-2].text.startswith('I took that as "Send it to someone to decide"')
    assert s.ruleset.rules[0].params["action"] == "review"


def test_typed_negative_and_you_pick() -> None:
    s = _session({1: "Meals up to $75 per person."})
    s2 = reply(s, _open(s).id, None, "don't allow it")
    assert s2.ruleset.rules[0].params["action"] == "block"
    s3 = reply(s, _open(s).id, None, "you pick")
    assert s3.ruleset.rules[0].params["action"] == "block"  # the suggested choice


def test_unclear_reply_asks_again_without_calling_it_a_rule() -> None:
    s = _session({1: "Meals up to $75 per person."})
    gap = _open(s)
    s = reply(s, gap.id, None, "hmm")
    assert "didn't catch which choice" in s.messages[-2].text
    assert _open(s).id == gap.id
