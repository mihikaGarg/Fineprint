"""The setup chat speaks plainly: no bare "Block it", progress, examples, a recap."""

from pathlib import Path

from compiler.extractor import extract_pdf_pages
from compiler.policy import draft_from_items
from compiler.policy_chat import PolicySession, describe, reply, start_session
from compiler.policy_offline import read_policy

POLICY_PDF = (
    Path(__file__).resolve().parents[2] / "fixtures" / "policies" / "northwind_te_policy.pdf"
)
BANNED = ("block it", "send for review", "block them", "always block", "and block")


def _session(pages: dict[int, str]) -> PolicySession:
    return start_session(draft_from_items(pages, "P", read_policy(pages), "offline"), "t", [])


def _walk(s: PolicySession) -> PolicySession:
    while not s.approved:
        gap = next(g for g in s.gaps if not g.resolved)
        s = reply(s, gap.id, gap.options[0].value, None)
    return s


def test_no_choice_anywhere_uses_vague_block_wording() -> None:
    pages = {p.page_number: p.raw_text for p in extract_pdf_pages(POLICY_PDF.read_bytes())}
    typed = {
        1: "Meals up to $75. Spousal travel is not reimbursable. Hotel rates should be reasonable."
    }
    for s in (_session(pages), _session(typed)):
        for gap in s.gaps:
            for option in gap.options:
                assert not any(b in option.label.lower() for b in BANNED), option.label


def test_questions_name_the_situation() -> None:
    s = _session({1: "Meals up to $75 per person."})
    assert "What should happen when a meal costs more than $75?" in s.messages[-1].text
    assert [o.label for o in s.gaps[0].options] == [
        "Don't allow it",
        "Allow it, but flag it for someone to check",
    ]


def test_progress_examples_and_final_recap() -> None:
    s = _session({1: "Meals up to $75. Gifts over $100 require the CEO's approval. No alcohol."})
    assert s.messages[-1].text.startswith("(1 of ")
    gap = next(g for g in s.gaps if not g.resolved)
    s = reply(s, gap.id, "review", None)
    confirmation = s.messages[-2].text
    assert "For example:" in confirmation and "flagged for review" in confirmation
    assert s.messages[-1].text.startswith("(2 of ")
    s = _walk(s)
    recap = next(m.text for m in s.messages if m.text.startswith("That's everything"))
    assert recap.count("\n• ") == len(s.ruleset.rules)


def test_rule_descriptions_are_plain() -> None:
    s = _walk(_session({1: "Meals up to $75. No alcohol. Never buy from Amazon."}))
    lines = {describe(r) for r in s.ruleset.rules}
    assert "Alcohol: not allowed" in lines
    assert "Purchases from Amazon: not allowed" in lines
    assert any(line.startswith("Meals over $75: ") for line in lines)


def test_progress_ignores_questions_answered_automatically() -> None:
    s = _session(
        {1: "Hotels up to $350 per night. Hotel rates should be reasonable. Receipts over $25."}
    )
    seen: list[str] = []
    while not s.approved:
        gap = next(g for g in s.gaps if not g.resolved)
        seen.append(s.messages[-1].text.split(")")[0] + ")")
        s = reply(s, gap.id, gap.options[0].value, None)
    numbered = [x for x in seen if x.startswith("(")]
    totals = [int(x.split(" of ")[1].rstrip(")")) for x in numbered]
    assert totals == sorted(
        totals, reverse=True
    )  # can shrink when a question is skipped, never grow
    assert [int(x[1:].split(" ")[0]) for x in numbered] == list(range(1, len(numbered) + 1))
