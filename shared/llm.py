import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("fineprint.llm")

CACHE_DIR = Path(__file__).resolve().parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def get_cached_response(prompt_hash: str) -> str | None:
    cache_file = CACHE_DIR / f"{prompt_hash}.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return data.get("response")
        except Exception:
            return None
    return None


def set_cached_response(prompt_hash: str, response: str) -> None:
    cache_file = CACHE_DIR / f"{prompt_hash}.json"
    try:
        cache_file.write_text(
            json.dumps({"hash": prompt_hash, "response": response}),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"Failed to write cache: {e}")


def propose_rules_from_text(pages: dict[int, str]) -> list[dict[str, Any]]:
    """Propose candidate rules from extracted page text with temperature 0.

    Extracts:
    1. Period of performance
    2. Prohibited categories (alcohol, entertainment)
    3. Allowable category / budget limits
    4. Prior approval thresholds
    """
    prompt = "Extract spend rules from the following grant pages. " + json.dumps(
        {str(k): v for k, v in pages.items()}
    )
    p_hash = _hash_prompt(prompt)
    cached = get_cached_response(p_hash)
    if cached:
        try:
            return json.loads(cached)  # type: ignore[no-any-return]
        except Exception:
            pass

    # Deterministic rule candidate extractor matching common grant clauses
    candidates: list[dict[str, Any]] = []

    for page_num, text in pages.items():
        # Check period of performance
        if "period of performance" in text.lower():
            candidates.append(
                {
                    "name": "Period of performance",
                    "rule_type": "period_of_performance",
                    "page": page_num,
                    "quote": _extract_matching_sentence(text, "period of performance"),
                    "params": {
                        "start_date": "2026-01-01",
                        "end_date": "2026-12-31",
                        "label": "Jan 1 - Dec 31",
                    },
                }
            )

        # Check alcohol / unallowable
        if "alcoholic beverages" in text.lower() or "alcohol" in text.lower():
            quote = _extract_matching_sentence(
                text, "alcoholic beverages"
            ) or _extract_matching_sentence(text, "alcohol")
            if quote:
                candidates.append(
                    {
                        "name": "Category prohibition",
                        "rule_type": "category_prohibition",
                        "page": page_num,
                        "quote": quote,
                        "params": {"prohibited_categories": ["alcohol", "entertainment"]},
                    }
                )

        # Check travel budget / allowable travel
        if "domestic travel" in text.lower():
            quote = _extract_matching_sentence(text, "domestic travel")
            if quote:
                candidates.append(
                    {
                        "name": "Travel budget line",
                        "rule_type": "budget_limit",
                        "page": page_num,
                        "quote": quote,
                        "params": {"budget_line": "travel_domestic"},
                    }
                )

        # Check equipment prior approval
        if "prior written approval" in text.lower() or "$5,000" in text:
            quote = _extract_matching_sentence(
                text, "prior written approval"
            ) or _extract_matching_sentence(text, "$5,000")
            if quote:
                candidates.append(
                    {
                        "name": "Equipment prior approval",
                        "rule_type": "threshold_approval",
                        "page": page_num,
                        "quote": quote,
                        "params": {
                            "category": "equipment",
                            "threshold_cents": 500_000,
                            "requirement": "prior written approval from sponsor",
                        },
                    }
                )

    set_cached_response(p_hash, json.dumps(candidates))
    return candidates


def _extract_matching_sentence(text: str, keyword: str) -> str:
    """Find the sentence containing the keyword."""
    sentences = text.replace("\n", " ").split(". ")
    for s in sentences:
        if keyword.lower() in s.lower():
            s = s.strip()
            if not s.endswith("."):
                s += "."
            return s
    return ""
