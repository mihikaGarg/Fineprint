"""The only entry point for LLM calls.

Every call goes through `complete_json`, which:
- returns a cached response when the same request was made before (keyed by a
  hash of model, effort, system prompt, user prompt and output schema), so
  reruns and demos are free and reproducible;
- logs model, cache key, token counts and latency, never prompt text or
  credentials;
- caps retries (the SDK retries 429/5xx/connection errors MAX_RETRIES times);
- forces structured JSON output against a schema.

Current Claude models reject sampling parameters, so temperature can't be set;
determinism comes from the cache instead.

The API key is read by the Anthropic SDK from the ANTHROPIC_API_KEY environment
variable. It is never passed, stored or logged here. Never import this from
/enforce.
"""

import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("fineprint.llm")

CACHE_DIR = Path(__file__).resolve().parent / ".cache"

DEFAULT_MODEL = "claude-opus-5-5"
MAX_RETRIES = 2
MAX_TOKENS = 16_000

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class LLMError(Exception):
    """The LLM call failed or returned something unusable."""


class LLMRefusal(LLMError):
    """The model declined the request."""


def _default_model() -> str:
    return os.environ.get("FINEPRINT_LLM_MODEL", DEFAULT_MODEL)


@dataclass(frozen=True)
class LLMRequest:
    system: str
    prompt: str
    schema: dict[str, Any]
    model: str = field(default_factory=_default_model)
    effort: Effort = "medium"
    max_tokens: int = MAX_TOKENS

    def cache_key(self) -> str:
        return hash_prompt(json.dumps(asdict(self), sort_keys=True))


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


Transport = Callable[[LLMRequest], LLMResponse]


def is_configured() -> bool:
    """True if an API key is available. Does not reveal or validate the key."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def anthropic_transport(request: LLMRequest) -> LLMResponse:
    """Send one request to the Claude API with JSON-schema output."""
    import anthropic

    client = anthropic.Anthropic(max_retries=MAX_RETRIES)
    try:
        response = client.beta.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            system=request.system,
            messages=[{"role": "user", "content": request.prompt}],
            output_config={
                "effort": request.effort,
                "format": {"type": "json_schema", "schema": request.schema},
            },
            # If the model declines, the API re-runs the request on Anthropic's
            # recommended fallback model instead of returning a refusal.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error {e.status_code}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Claude API") from e

    if response.stop_reason == "refusal":
        raise LLMRefusal("The model declined to process this document")
    if response.stop_reason == "max_tokens":
        raise LLMError("Response was cut off at max_tokens")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise LLMError("Response contained no text block")
    return LLMResponse(
        text=text,
        model=response.model,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )


def complete_json(
    request: LLMRequest,
    transport: Transport = anthropic_transport,
    *,
    cache: bool = True,
) -> Any:
    """Run a request (or return its cached result) and parse the JSON output.

    Pass cache=False for replayed or fake answers so they never enter the real cache.
    """
    key = request.cache_key()
    cached = get_cached_response(key) if cache else None
    if cached is not None:
        logger.info("llm cache hit key=%s model=%s", key[:12], request.model)
        return json.loads(cached)

    start = time.perf_counter()
    response = transport(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "llm call key=%s model=%s input_tokens=%d output_tokens=%d ms=%.0f",
        key[:12],
        response.model,
        response.input_tokens,
        response.output_tokens,
        elapsed_ms,
    )

    try:
        data = json.loads(response.text)
    except json.JSONDecodeError as e:
        raise LLMError("Model output was not valid JSON") from e

    if cache:
        set_cached_response(key, response.text)
    return data


def hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def get_cached_response(prompt_hash: str) -> str | None:
    cache_file = CACHE_DIR / f"{prompt_hash}.json"
    if not cache_file.exists():
        return None
    try:
        data: dict[str, str] = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Unreadable cache entry %s", prompt_hash[:12])
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
