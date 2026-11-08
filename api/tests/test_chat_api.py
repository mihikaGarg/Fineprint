from typing import Any

from fastapi.testclient import TestClient

import api.main as api_main

client = TestClient(api_main.app)


def finish(session: dict[str, Any]) -> dict[str, Any]:
    while not session["approved"]:
        gaps: list[dict[str, Any]] = session["gaps"]
        gap = next(g for g in gaps if not g["resolved"])
        session = client.post(
            f"/api/chat/{session['session_id']}/reply",
            json={"gap_id": gap["id"], "value": gap["options"][0]["value"]},
        ).json()
    return session


def test_sample_policy_chat_with_grant_then_batch() -> None:
    res = client.post("/api/chat/start", data={"sample": "northwind", "link_demo_grant": "true"})
    assert res.status_code == 200
    s: dict[str, Any] = res.json()
    assert s["source"] == "northwind_te_policy.pdf" and s["drafter"] == "offline"
    assert s["grant_ids"] and any(g["kind"] == "conflict" for g in s["gaps"])
    s = finish(s)

    items = client.post(
        "/api/batch", json={"ruleset_ids": [s["session_id"], *s["grant_ids"]]}
    ).json()
    by_id = {i["expense"]["id"]: i["result"] for i in items}
    assert len(items) == 16
    assert by_id["NW-1001"]["verdict"] == "ALLOWED"  # economy flight
    assert by_id["NW-1008"]["verdict"] == "BLOCKED"  # Amazon Marketplace
    assert by_id["NW-1010"]["verdict"] == "BLOCKED"  # fundraising, banned by the grant
    assert by_id["NW-1011"]["verdict"] == "BLOCKED"  # after the grant period
    assert by_id["NW-1013"]["verdict"] == "ALLOWED"  # software with manager + IT approval
    sources = {t["source"] for r in by_id.values() for t in r["traces"] if t["outcome"] != "PASS"}
    assert sources == {"grant", "policy"}


def test_upload_text_file_and_reply_errors() -> None:
    res = client.post(
        "/api/chat/start",
        files={"file": ("rules.txt", b"No alcohol. Meals up to $75.", "text/plain")},
    )
    s = res.json()
    assert s["source"] == "rules.txt"
    bad = client.post(
        f"/api/chat/{s['session_id']}/reply", json={"gap_id": s["gaps"][0]["id"], "value": "nope"}
    )
    assert bad.status_code == 400
    assert client.post("/api/chat/start", data={}).status_code == 400
    assert "Fineprint policy assistant" in client.get("/chat").text


def test_full_app_flow_state_budget_and_reset() -> None:
    client.post("/api/reset")
    assert client.get("/api/state").json()["rulesets"] == []
    grant = client.post("/api/compile/demo").json()
    gid = grant["ruleset"]["grant_id"]
    assert client.get(f"/api/grants/{gid}").json()["coverage"]["total"] > 0
    client.post(f"/api/rulesets/{gid}/approve", json={})
    s = client.post("/api/chat/start", data={"sample": "northwind", "grant_ids": gid}).json()
    assert s["grant_ids"] == [gid]
    finish(s)

    state = client.get("/api/state").json()
    assert {r["kind"] for r in state["rulesets"]} == {"grant", "policy"}
    assert all(r["approved"] == r["rules"] for r in state["rulesets"])

    before = state["budget"]["lines"]["travel_domestic"]["spent_cents"]
    expense = {
        "id": "T1",
        "amount_cents": 20_000,
        "date": "2026-06-20",
        "merchant": "Amtrak",
        "category": "travel_domestic",
        "has_receipt": True,
    }
    item = client.post("/api/expenses/check", json={"expense": expense}).json()
    assert item["result"]["verdict"] == "ALLOWED" and item["recorded_spend"] is True
    after = client.get("/api/state").json()["budget"]["lines"]["travel_domestic"]["spent_cents"]
    assert after == before + 20_000

    batch = client.post("/api/expenses/sample-batch", json={}).json()
    assert len(batch) == 16
    state = client.get("/api/state").json()
    assert state["expenses_checked"] == 17
    assert "Fineprint" in client.get("/app").text

    client.post("/api/reset")
    state = client.get("/api/state").json()
    assert state["rulesets"] == [] and state["expenses_checked"] == 0
    assert state["budget"]["lines"]["travel_domestic"]["spent_cents"] == before
