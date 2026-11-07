"""Test-wide safety: no test may use a real API key or the shared LLM cache."""

from pathlib import Path

import pytest

import shared.llm


@pytest.fixture(autouse=True)
def _isolate_llm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("FINEPRINT_PROPOSER", "keyword")
    monkeypatch.setattr(shared.llm, "CACHE_DIR", tmp_path / "llm-cache")
