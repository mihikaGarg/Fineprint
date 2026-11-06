import re

from contracts.models import RuleCitation


def verify_citation(
    pages: dict[int, str],
    page_number: int,
    candidate_quote: str,
    context_window: int = 30,
) -> RuleCitation | None:
    """Verify that a candidate quote exists verbatim in the extracted page text.

    Returns a verified RuleCitation with exact char offsets and surrounding context,
    or None if the quote cannot be verified.
    """
    cleaned_quote = candidate_quote.strip()
    if not cleaned_quote:
        return None

    page_text = pages.get(page_number)
    if page_text is None:
        return None

    # 1. Exact substring match
    idx = page_text.find(cleaned_quote)
    if idx != -1:
        start = idx
        end = idx + len(cleaned_quote)
        prefix = page_text[max(0, start - context_window) : start]
        suffix = page_text[end : min(len(page_text), end + context_window)]
        return RuleCitation(
            page=page_number,
            quote=cleaned_quote,
            char_start=start,
            char_end=end,
            prefix=prefix,
            suffix=suffix,
        )

    # 2. Whitespace-normalized fallback (handles line breaks or multi-space formatting)
    pattern = re.escape(cleaned_quote)
    # Allow arbitrary whitespace between words
    pattern = re.sub(r"\\\s+", r"\\s+", pattern)
    match = re.search(pattern, page_text)
    if match:
        start = match.start()
        end = match.end()
        exact_text = page_text[start:end]
        prefix = page_text[max(0, start - context_window) : start]
        suffix = page_text[end : min(len(page_text), end + context_window)]
        return RuleCitation(
            page=page_number,
            quote=exact_text,
            char_start=start,
            char_end=end,
            prefix=prefix,
            suffix=suffix,
        )

    # Unverifiable quote is rejected
    return None
