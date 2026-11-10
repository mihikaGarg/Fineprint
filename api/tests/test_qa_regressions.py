"""Regression tests for bugs found in the QA pass."""

import io
from typing import Any

from fastapi.testclient import TestClient
from pypdf import PdfWriter

import api.main as api_main

client = TestClient(api_main.app)


def expense(**kw: Any) -> dict[str, Any]:
    base = {
        "id": "e",
        "amount_cents": 5000,
        "date": "2026-06-15",
        "merchant": "Shop",
        "category": "supplies",
        "has_receipt": True,
    }
    return {**base, **kw}


def answer_all(s: dict[str, Any]) -> dict[str, Any]:
    while not s["approved"]:
        gaps: list[dict[str, Any]] = s["gaps"]
        gap = next(g for g in gaps if not g["resolved"])
        s = client.post(
            f"/api/chat/{s['session_id']}/reply",
            json={"gap_id": gap["id"], "value": gap["options"][0]["value"]},
        ).json()
    return s


def demo_grant() -> str:
    gid: str = client.post("/api/compile/demo").json()["ruleset"]["grant_id"]
    client.post(f"/api/rulesets/{gid}/approve", json={})
    return gid


def test_damaged_and_textless_pdfs_get_clear_errors() -> None:
    assert (
        client.post(
            "/api/compile", files={"file": ("bad.pdf", b"not a pdf", "application/pdf")}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/chat/start", files={"file": ("bad.pdf", b"nope", "application/pdf")}
        ).status_code
        == 400
    )
    w = PdfWriter()
    w.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    w.write(buf)
    res = client.post(
        "/api/compile", files={"file": ("scan.pdf", buf.getvalue(), "application/pdf")}
    )
    assert res.status_code == 400 and "scanned" in res.json()["detail"]


def test_rulebook_respects_open_chat_questions_and_stays_in_sync() -> None:
    client.post("/api/reset")
    s = client.post(
        "/api/chat/start",
        data={"text": "Meals up to $75. Gifts over $100 require the CEO's approval."},
    ).json()
    sid = s["session_id"]
    cards = client.get(f"/api/rulesets/{sid}/cards").json()
    assert all(not c["can_approve"] for c in cards)  # both rules still have a question
    rs = client.post(f"/api/rulesets/{sid}/approve", json={}).json()
    assert all(r["status"] == "proposed" for r in rs["rules"])

    gaps: list[dict[str, Any]] = s["gaps"]
    first = next(g for g in gaps if not g["resolved"])
    done = first["rule_id"] or first["rule_ids"][0]
    s = client.post(
        f"/api/chat/{sid}/reply",
        json={"gap_id": first["id"], "value": first["options"][0]["value"]},
    ).json()
    client.post(f"/api/rulesets/{sid}/approve", json={"rule_ids": [done]})
    gaps = s["gaps"]
    nxt = next(g for g in gaps if not g["resolved"])
    client.post(
        f"/api/chat/{sid}/reply", json={"gap_id": nxt["id"], "value": nxt["options"][0]["value"]}
    )
    status = next(
        r["status"] for r in client.get(f"/api/rulesets/{sid}").json()["rules"] if r["id"] == done
    )
    assert status == "approved"


def test_role_names_match_however_they_are_typed() -> None:
    client.post("/api/reset")
    s = answer_all(
        client.post(
            "/api/chat/start",
            data={
                "text": "Expenses of $1,000 or more need finance director approval. "
                "Receipts over $25."
            },
        ).json()
    )
    body = {
        "expense": expense(amount_cents=200_000, approvals=["Finance Director"]),
        "ruleset_ids": [s["session_id"]],
        "record": False,
    }
    assert client.post("/api/expenses/check", json=body).json()["result"]["verdict"] == "ALLOWED"


def test_budget_spend_and_travel_categories() -> None:
    client.post("/api/reset")
    gid = demo_grant()
    s = answer_all(
        client.post(
            "/api/chat/start", data={"text": "Receipts over $25. No alcohol.", "grant_ids": gid}
        ).json()
    )

    def state() -> int:
        lines = client.get(f"/api/grants/{gid}/budget").json()["lines"]
        return next(line["spent_cents"] for line in lines if line["line"] == "travel_domestic")

    start = state()
    client.post(
        "/api/expenses/check",
        json={
            "expense": expense(amount_cents=30_000, category="travel_domestic"),
            "ruleset_ids": [s["session_id"]],
        },
    )
    assert state() == start  # policy-only check: no grant, no grant spend
    client.post(
        "/api/expenses/check",
        json={"expense": expense(amount_cents=40_000, category="airfare"), "ruleset_ids": [gid]},
    )
    assert state() == start + 40_000  # flights come off the travel budget
    res = client.post(
        "/api/expenses/check",
        json={
            "expense": expense(amount_cents=790_000, category="lodging"),
            "ruleset_ids": [gid],
            "record": False,
        },
    ).json()
    assert res["result"]["verdict"] == "BLOCKED"  # over what's left in travel


def test_chat_does_not_create_clashing_or_duplicate_caps() -> None:
    client.post("/api/reset")
    s = answer_all(
        client.post(
            "/api/chat/start",
            data={"text": "Hotels up to $350 per night. Hotel rates should be reasonable."},
        ).json()
    )
    caps = [r for r in s["ruleset"]["rules"] if r["rule_type"] == "per_item_cap"]
    assert len(caps) == 1 and caps[0]["params"]["cap_cents"] == 35_000
    assert any("already covered" in m["text"] for m in s["messages"])

    s2 = client.post("/api/chat/start", data={"text": "Meals up to $75."}).json()
    s2 = client.post(
        f"/api/chat/{s2['session_id']}/reply", json={"text": "Meals up to $75."}
    ).json()
    assert len(s2["ruleset"]["rules"]) == 1
    assert any(m["text"].startswith("You already have") for m in s2["messages"])


def test_unknown_category_rejected() -> None:
    res = client.post(
        "/api/expenses/check", json={"expense": expense(category="spaceship"), "record": False}
    )
    assert res.status_code == 422


def test_grant_budget_comes_from_the_agreement_and_missing_lines_can_be_entered() -> None:
    client.post("/api/reset")
    gid = demo_grant()
    b = client.get(f"/api/grants/{gid}/budget").json()
    travel = next(line for line in b["lines"] if line["line"] == "travel_domestic")
    assert travel["allocated_cents"] == 800_000 and travel["source"].startswith("p. 5:")
    assert b["missing"] == []

    # A grant whose rules mention a budget line the agreement doesn't price.
    pdf_text_grant = client.post(
        "/api/compile",
        files={"file": ("demo.pdf", api_main.DEMO_PDF.read_bytes(), "application/pdf")},
    ).json()
    assert pdf_text_grant["budget"]  # same document, budget re-read

    b = client.post(
        f"/api/grants/{gid}/budget", json={"line": "travel_foreign", "allocated_cents": 300_000}
    ).json()
    foreign = next(line for line in b["lines"] if line["line"] == "travel_foreign")
    assert foreign["source"] == "entered by you" and foreign["remaining_cents"] == 300_000
    assert (
        client.post(
            f"/api/grants/{gid}/budget", json={"line": "x", "allocated_cents": 12.5}
        ).status_code
        == 422
    )


def test_each_grant_keeps_its_own_budget() -> None:
    from compiler.pipeline import compile_pages_full

    client.post("/api/reset")
    gid = demo_grant()
    other = compile_pages_full(
        {
            1: "Domestic travel necessary for the project is allowable within the approved budget.",
            2: "Approved budget\nDomestic travel: $500",
        },
        "grant_small",
        "Small grant",
        status="approved",
    )
    api_main._compile_response(other)  # pyright: ignore[reportPrivateUsage]
    trip = expense(amount_cents=60_000, category="travel_domestic")
    big = client.post(
        "/api/expenses/check", json={"expense": trip, "ruleset_ids": [gid], "record": False}
    ).json()
    small = client.post(
        "/api/expenses/check",
        json={"expense": trip, "ruleset_ids": ["grant_small"], "record": False},
    ).json()
    assert big["result"]["verdict"] == "ALLOWED"  # $600 of $8,000
    assert small["result"]["verdict"] == "BLOCKED"  # $600 of $500
