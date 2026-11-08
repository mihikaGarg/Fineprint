from fastapi.testclient import TestClient

from api.main import app
from fixtures.sample_data import SAMPLE_BUDGET, SAMPLE_EXPENSES, SAMPLE_RULESET

client = TestClient(app)


def test_api_health() -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_api_fixtures() -> None:
    res = client.get("/api/fixtures")
    assert res.status_code == 200
    data = res.json()
    assert "ruleset" in data
    assert "budget" in data
    assert "expenses" in data


def test_api_enforce_endpoint() -> None:
    payload = {
        "expense": SAMPLE_EXPENSES[0],
        "ruleset": SAMPLE_RULESET.model_dump(),
        "budget_state": SAMPLE_BUDGET.model_dump(),
    }
    res = client.post("/api/enforce", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] == "ALLOWED"
    assert len(data["traces"]) > 0
    assert data["latency_ms"] < 50.0


def test_fixture_citations_verify_against_sample_pages() -> None:
    from fixtures.sample_data import SAMPLE_PAGES, SAMPLE_REJECTED

    assert SAMPLE_REJECTED == []
    assert len(SAMPLE_RULESET.rules) == 5
    for rule in SAMPLE_RULESET.rules:
        c = rule.citation
        assert SAMPLE_PAGES[c.page][c.char_start : c.char_end] == c.quote


def test_api_rejects_float_amounts() -> None:
    payload = {
        "expense": {**SAMPLE_EXPENSES[0], "amount_cents": 412.5},
        "ruleset": SAMPLE_RULESET.model_dump(mode="json"),
        "budget_state": SAMPLE_BUDGET.model_dump(mode="json"),
    }
    assert client.post("/api/enforce", json=payload).status_code == 422


def test_compile_demo_offline_uses_keyword_proposer() -> None:
    res = client.post("/api/compile/demo")
    assert res.status_code == 200
    data = res.json()
    assert data["proposer"] == "keyword"
    assert data["verified_count"] == 4
