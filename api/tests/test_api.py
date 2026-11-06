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
