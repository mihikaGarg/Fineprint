"""Fail if anything in the repo looks like an Anthropic API key."""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
# Built in two parts so this file doesn't match itself.
KEY_RE = re.compile("sk-" + r"ant-[A-Za-z0-9_\-]{20,}")


def test_no_api_keys_in_repo() -> None:
    try:
        listed = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git not available")

    offenders: list[str] = []
    for name in listed:
        path = REPO / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if KEY_RE.search(text):
            offenders.append(name)
    assert offenders == [], f"Possible API key in: {offenders}"
