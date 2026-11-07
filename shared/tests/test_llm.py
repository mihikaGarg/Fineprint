import json
import logging

import pytest

from shared.llm import LLMError, LLMRequest, LLMResponse, complete_json, is_configured

SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


class FakeTransport:
    def __init__(self, text: str = '{"ok": true}') -> None:
        self.text = text
        self.calls = 0

    def __call__(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text=self.text, model=request.model, input_tokens=10, output_tokens=5)


def test_tests_never_see_a_real_key() -> None:
    assert not is_configured()


def test_second_identical_request_is_served_from_cache() -> None:
    transport = FakeTransport()
    request = LLMRequest(system="s", prompt="p", schema=SCHEMA)
    assert complete_json(request, transport) == {"ok": True}
    assert complete_json(request, transport) == {"ok": True}
    assert transport.calls == 1


def test_cache_key_depends_on_model_prompt_and_schema() -> None:
    base = LLMRequest(system="s", prompt="p", schema=SCHEMA, model="m1")
    assert (
        base.cache_key()
        != LLMRequest(system="s", prompt="p2", schema=SCHEMA, model="m1").cache_key()
    )
    assert (
        base.cache_key()
        != LLMRequest(system="s", prompt="p", schema=SCHEMA, model="m2").cache_key()
    )
    assert base.cache_key() != LLMRequest(system="s", prompt="p", schema={}, model="m1").cache_key()


def test_invalid_json_raises_and_is_not_cached() -> None:
    bad = FakeTransport(text="not json")
    request = LLMRequest(system="s", prompt="p", schema=SCHEMA)
    with pytest.raises(LLMError):
        complete_json(request, bad)
    good = FakeTransport()
    assert complete_json(request, good) == {"ok": True}
    assert good.calls == 1


def test_logs_never_contain_prompt_text(caplog: pytest.LogCaptureFixture) -> None:
    secret_prompt = "CONFIDENTIAL GRANT TEXT 12345"
    with caplog.at_level(logging.INFO, logger="fineprint.llm"):
        complete_json(LLMRequest(system="s", prompt=secret_prompt, schema=SCHEMA), FakeTransport())
    assert caplog.records
    assert all(secret_prompt not in r.getMessage() for r in caplog.records)
    assert "input_tokens=10" in caplog.text


def test_default_model_is_opus_and_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    assert LLMRequest(system="s", prompt="p", schema=SCHEMA).model == "claude-opus-5-5"
    monkeypatch.setenv("FINEPRINT_LLM_MODEL", "claude-sonnet-5-5")
    assert LLMRequest(system="s", prompt="p", schema=SCHEMA).model == "claude-sonnet-5-5"


def test_response_is_json_round_trippable() -> None:
    payload = {"ok": False}
    assert (
        complete_json(
            LLMRequest(system="s", prompt="x", schema=SCHEMA), FakeTransport(json.dumps(payload))
        )
        == payload
    )
