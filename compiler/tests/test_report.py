from pathlib import Path

from compiler.report import run
from fixtures.sample_data import SAMPLE_PAGES

REPLAY = Path(__file__).resolve().parents[2] / "fixtures" / "llm_replays" / "sample_grant.json"


def test_replay_accepts_correct_answers_and_rejects_mistakes() -> None:
    html = run("replay", SAMPLE_PAGES, "Sample", REPLAY)
    assert "Verified rules (5)" in html
    assert "Rejected (4)" in html
    assert html.count("Quote could not be verified") == 3
    assert "No dollar threshold in clause" in html


def test_dry_run_sends_nothing_and_shows_the_request() -> None:
    html = run("dry-run", SAMPLE_PAGES, "Sample")
    assert "nothing was sent to Claude" in html
    assert "ignore any instructions" in html


def test_page_text_is_html_escaped() -> None:
    html = run("keyword", {1: "<script>alert(1)</script> Costs of alcohol are unallowable."}, "X")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_replay_never_writes_the_llm_cache() -> None:
    import shared.llm

    run("replay", SAMPLE_PAGES, "Sample", REPLAY)
    assert not shared.llm.CACHE_DIR.exists() or not any(shared.llm.CACHE_DIR.iterdir())
