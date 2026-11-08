import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from shared.llm import LLMRequest, LLMResponse

client = TestClient(api_main.app)
TEXT = "No alcohol. Meals up to $75. Anything over $5,000 needs the finance director."
ANSWER: dict[str, Any] = {
    "rules": [
        {
            "rule_type": "category_prohibition",
            "quote": "No alcohol.",
            "categories": ["alcohol"],
            "action": "unspecified",
            "approver_role": "",
            "merchants": [],
            "questions": [],
        },
        {
            "rule_type": "per_item_cap",
            "quote": "Meals up to $75.",
            "categories": ["meals"],
            "action": "unspecified",
            "approver_role": "",
            "merchants": [],
            "questions": [],
        },
        {
            "rule_type": "approval_required",
            "quote": "Anything over $5,000 needs the finance director.",
            "categories": [],
            "action": "review",
            "approver_role": "finance_director",
            "merchants": [],
            "questions": [],
        },
    ],
    "not_rules": [],
}


@pytest.fixture(autouse=True)
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    def transport(request: LLMRequest) -> LLMResponse:
        return LLMResponse(text=json.dumps(ANSWER), model="fake", input_tokens=1, output_tokens=1)

    monkeypatch.setattr(api_main, "LLM_TRANSPORT", transport)


def expense(amount: int, category: str, **kw: Any) -> dict[str, Any]:
    return {
        "id": "e",
        "amount_cents": amount,
        "date": "2026-06-15",
        "merchant": "Cafe",
        "category": category,
        **kw,
    }


def test_policy_flow_draft_answer_approve_enforce() -> None:
    draft = client.post("/api/policy/draft", json={"text": TEXT}).json()
    did = draft["draft_id"]
    [q] = draft["questions"]
    assert q["field"] == "action"

    cards = client.get(f"/api/rulesets/{did}/cards").json()
    blocked_card = next(c for c in cards if c["open_questions"])
    assert blocked_card["can_approve"] is False and blocked_card["examples"] == []

    # Approving now skips the rule with an open question.
    rs = client.post(f"/api/rulesets/{did}/approve", json={}).json()
    assert [r["status"] for r in rs["rules"]] == ["approved", "proposed", "approved"]

    draft = client.post(f"/api/policy/{did}/answers", json={"answers": {q["id"]: "review"}}).json()
    assert draft["questions"] == []
    rs = client.post(f"/api/rulesets/{did}/approve", json={}).json()
    assert all(r["status"] == "approved" for r in rs["rules"])

    cards = client.get(f"/api/rulesets/{did}/cards").json()
    meal_card = next(c for c in cards if c["rule"]["rule_type"] == "per_item_cap")
    assert [e["verdict"] for e in meal_card["examples"]] == ["ALLOWED", "ALLOWED", "NEEDS_REVIEW"]

    # Check against the sample grant and the company policy together.
    body: dict[str, Any] = {"budget_state": {"lines": {}}, "ruleset_ids": ["grant_bbs_2026", did]}
    res = client.post("/api/enforce", json={**body, "expense": expense(9_000, "meals")}).json()
    assert res["verdict"] == "NEEDS_REVIEW"
    deciding = next(t for t in res["traces"] if t["outcome"] != "PASS")
    assert deciding["source"] == "policy" and deciding["fix"] == "Allowed at $75 or less"

    res = client.post(
        "/api/enforce",
        json={**body, "expense": expense(600_000, "software", approvals=["finance_director"])},
    ).json()
    assert res["verdict"] == "ALLOWED"


def test_bad_answer_is_rejected() -> None:
    draft = client.post("/api/policy/draft", json={"text": TEXT}).json()
    res = client.post(
        f"/api/policy/{draft['draft_id']}/answers",
        json={"answers": {draft["questions"][0]["id"]: "yolo"}},
    )
    assert res.status_code == 400


def test_compiled_grant_rules_start_proposed_and_report_coverage() -> None:
    data = client.post("/api/compile/demo").json()
    assert all(r["status"] == "proposed" for r in data["ruleset"]["rules"])
    cov = data["coverage"]
    assert cov["total"] == cov["rules"] + cov["flagged"] + cov["rejected"] + cov["no_rule"]
    assert cov["rules"] >= 4


def test_policy_needs_a_key_without_a_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "LLM_TRANSPORT", api_main.anthropic_transport)
    assert client.post("/api/policy/draft", json={"text": TEXT}).status_code == 503
