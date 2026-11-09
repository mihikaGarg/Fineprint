from pathlib import Path

import pytest

from compiler.extractor import extract_pdf_pages
from compiler.policy import draft_from_items
from compiler.policy_chat import (
    PolicySession,
    ReplyError,
    reply,
    start_session,
    verify_session_citations,
)
from compiler.policy_offline import read_policy

POLICY_PDF = (
    Path(__file__).resolve().parents[2] / "fixtures" / "policies" / "northwind_te_policy.pdf"
)


def session_from(pages: dict[int, str]) -> PolicySession:
    return start_session(draft_from_items(pages, "P", read_policy(pages), "offline"), "test", [])


def next_gap(s: PolicySession):
    return next(g for g in s.gaps if not g.resolved)


def test_enterprise_policy_is_read_with_every_approval_tier() -> None:
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages(POLICY_PDF.read_bytes())}
    s = session_from(pages)
    roles = {
        r.params.get("approver_role") for r in s.ruleset.rules if r.rule_type == "approval_required"
    }
    assert roles == {"manager", "department_director", "cfo", "provost", "it"}
    alcohol = next(
        r for r in s.ruleset.rules if "alcohol" in r.params.get("prohibited_categories", [])
    )
    assert alcohol.params["prohibited_categories"] == [
        "alcohol"
    ]  # not "entertainment" from the exception
    kinds = [g.kind for g in s.gaps]
    assert (
        kinds.count("exception") == 2
        and kinds.count("vague") == 2
        and kinds.count("unsupported") == 1
    )
    # Each approval rule gets its own question, with choices naming its approver.
    labels = [o.label for g in s.gaps if g.field == "action" for o in g.options]
    assert "Send them to the CFO to approve or reject" in labels
    assert "Reject gifts of $100 or more without provost sign-off" in labels


def test_full_conversation_ends_with_approved_cited_rules() -> None:
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages(POLICY_PDF.read_bytes())}
    s = session_from(pages)
    while not s.approved:
        g = next_gap(s)
        s = reply(s, g.id, g.options[0].value, None)
    assert all(r.status == "approved" for r in s.ruleset.rules)
    assert verify_session_citations(s)
    assert s.messages[-1].text.startswith("Approved.")


def test_vague_answer_by_typed_amount_creates_rule_citing_the_chat() -> None:
    s = session_from({1: "Hotel rates should be reasonable. Receipts over $25. No alcohol."})
    g = next(x for x in s.gaps if x.kind == "vague")
    s = reply(s, g.id, None, "275")
    cap = next(r for r in s.ruleset.rules if r.rule_type == "per_item_cap")
    assert cap.params["cap_cents"] == 27_500 and cap.params["categories"] == ["lodging"]
    assert cap.citation.page == s.chat_page
    assert "reasonable" in cap.params["clarifications"][0]["question"]
    assert verify_session_citations(s)


def test_missing_topics_are_asked_and_answers_become_rules() -> None:
    s = session_from({1: "Meals up to $75."})
    assert {g.id for g in s.gaps} >= {"missing:receipts", "missing:approvals", "missing:alcohol"}
    s = reply(s, "missing:approvals", "director:1000000", None)
    rule = next(r for r in s.ruleset.rules if r.rule_type == "approval_required")
    assert (
        rule.params["approver_role"] == "director" and rule.params["threshold_cents"] == 1_000_000
    )
    assert s.pages[s.chat_page].endswith("Expenses of $10,000 or more need director approval.")


def test_free_text_adds_rules_mid_conversation() -> None:
    s = session_from({1: "Meals up to $75."})
    s = reply(s, None, None, "Gifts over $100 require the CEO's approval.")
    gift = next(r for r in s.ruleset.rules if r.rule_type == "approval_required")
    assert gift.params["approver_role"] == "ceo"
    assert (
        next_gap(s).rule_id == gift.id or gift.id in next_gap(s).rule_ids
    )  # its question comes next
    s2 = reply(s, None, None, "hello there")
    assert "couldn't turn that into a rule" in s2.messages[-2].text


def test_answers_must_be_valid_options() -> None:
    s = session_from({1: "Meals up to $75."})
    g = next_gap(s)
    with pytest.raises(ReplyError):
        reply(s, g.id, "approve_everything", None)


def test_unapproved_rules_stay_proposed_until_final_approval() -> None:
    s = session_from({1: "No alcohol. Receipts over $25."})
    while next_gap(s).kind != "final":
        g = next_gap(s)
        s = reply(s, g.id, g.options[-1].value, None)
    assert all(r.status == "proposed" for r in s.ruleset.rules)
    s = reply(s, "final", "approve", None)
    assert all(r.status == "approved" for r in s.ruleset.rules)
