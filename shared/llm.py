"""The only entry point for LLM calls.

Currently provides the response cache (keyed by prompt hash) and logger that
every LLM call must use. The client call itself (temperature 0 for
extraction/classification, retry cap) is not wired up yet; the compiler's
proposer is deterministic until it is. Never import this from /enforce.
"""

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger("fineprint.llm")

CACHE_DIR = Path(__file__).resolve().parent / ".cache"


def hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def get_cached_response(prompt_hash: str) -> str | None:
    cache_file = CACHE_DIR / f"{prompt_hash}.json"
    if not cache_file.exists():
        return None
    try:
        data: dict[str, str] = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Unreadable cache entry %s", prompt_hash)
        return None
    return data.get("response")


def set_cached_response(prompt_hash: str, response: str) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"{prompt_hash}.json"
    try:
        cache_file.write_text(
            json.dumps({"hash": prompt_hash, "response": response}),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("Failed to write cache: %s", e)
