# Citation verifier

Branch: `a/citation-verifier` · Owner: A

## Scope
- [ ] Tests first
- [ ] Locate quote in page text deterministically and fill char_start/char_end (LLM never supplies offsets)
- [ ] Reject rules where page_text[start:end] != quote or document doesn't match

## Done when
Unverifiable rules are always rejected, with a reason logged.
