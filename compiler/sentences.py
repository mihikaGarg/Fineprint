"""Split document text into sentences and headings, with exact offsets.

PDF text has hard line breaks wherever a line wrapped, so a newline usually
means nothing. A segment ends:
- after "." or ";" followed by whitespace, unless the period belongs to an
  abbreviation ("No.", "e.g.", "U.S.") or to a heading number ("Article 2.",
  "1." at the start of a line);
- at a newline, if the next line starts a heading or numbered clause
  ("Article 5", "5.2", "§", "(a)", "Exhibit B"), or the current line is a short
  heading on its own ("Term", "Purpose and Scope").

Segments are exact substrings of the input, so citations built from them verify.
"""

import re
from dataclasses import dataclass
from itertools import pairwise

ABBREVIATIONS = {
    "no", "nos", "e.g", "i.e", "u.s", "dr", "mr", "mrs", "ms", "vs", "etc", "inc", "corp", "co",
    "st", "rev", "fig", "sec", "art", "approx", "dept", "est", "jr", "sr", "ltd", "pp", "p",
}  # fmt: skip
HEADING_WORDS = r"(?:Article|Section|Exhibit|Schedule|Appendix|Attachment|Part|Chapter)"
NEXT_LINE_HEADING_RE = re.compile(
    r"^\s*(?:§|" + HEADING_WORDS + r"\b|\d+(?:\.\d+)*\.?\s|\((?:[a-z]|[ivx]+|\d+)\)\s)"
)
LABEL_BEFORE_PERIOD_RE = re.compile(
    r"^\s*(?:" + HEADING_WORDS + r"\s+[\w.-]+|\d+(?:\.\d+)*|[A-Z]|[ivxlc]+)$", re.IGNORECASE
)
SENTENCE_END_RE = re.compile(r"[.;](?=\s)")
TABLE_ROW_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?\s*$")  # "Domestic travel: $8,000"
TERMINAL = ".;:!?"
LIST_ITEM_MAX_WORDS = 10
# A line ending in one of these is mid-sentence, never a finished list item.
CONTINUES = {
    "the", "a", "an", "of", "to", "and", "or", "unless", "except", "for", "with", "by", "in",
    "on", "at", "from", "that", "which", "who", "if", "than", "as", "be", "is", "are", "not",
}  # fmt: skip
MINOR_WORDS = {"and", "or", "of", "the", "a", "an", "for", "to", "in", "on", "&", "with", "by"}


@dataclass(frozen=True)
class Segment:
    start: int
    end: int
    text: str
    heading: bool  # a title or section heading, not a sentence


def _is_heading(text: str) -> bool:
    """Short, unpunctuated, and numbered or Title Case, with no amount in it."""
    words = re.findall(r"[A-Za-z0-9§][\w'§.-]*", re.sub(r"\([^)]*\)", "", text))
    if not words or len(words) > 10 or "$" in text or text.rstrip()[-1] in TERMINAL:
        return False
    if NEXT_LINE_HEADING_RE.match(text):
        return True
    alpha = [w for w in words if w[0].isalpha()]
    return bool(alpha) and all(w[0].isupper() or w.lower() in MINOR_WORDS for w in alpha)


def _line_bounds(text: str, pos: int) -> tuple[int, int]:
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return start, len(text) if end == -1 else end


def split_sentences(text: str) -> list[Segment]:
    breaks: set[int] = set()

    for m in SENTENCE_END_RE.finditer(text):
        i = m.start()
        if text[i] == ".":
            line_start, _ = _line_bounds(text, i)
            before = text[line_start:i]
            word = re.search(r"([A-Za-z][A-Za-z.]*)$", before)
            if word and word.group(1).lower().rstrip(".") in ABBREVIATIONS:
                continue
            if LABEL_BEFORE_PERIOD_RE.match(before):  # "Article 2." / "1." heading numbers
                continue
        breaks.add(i + 1)

    segment_start = 0
    for m in re.finditer(r"\n", text):
        j = m.start()
        if any(segment_start < b <= j for b in breaks):
            segment_start = max(b for b in breaks if b <= j)
        line_start, _ = _line_bounds(text, j)
        line = text[line_start:j]
        next_start, next_end = j + 1, _line_bounds(text, j + 1)[1]
        next_line = text[next_start:next_end]
        starts_segment = text[segment_start:line_start].strip() == ""
        is_row = bool(TABLE_ROW_RE.search(line))
        # A short line on its own followed by a capitalised line is a list item (typed
        # rules); wrapped PDF text fills the line, so it doesn't qualify.
        last_word = line.split()[-1].lower() if line.split() else ""
        is_list_item = (
            starts_segment
            and len(line.split()) <= LIST_ITEM_MAX_WORDS
            and next_line[:1].isupper()
            and last_word not in CONTINUES
        )
        if (
            NEXT_LINE_HEADING_RE.match(next_line)
            or is_row
            or is_list_item
            or (starts_segment and _is_heading(line))
        ):
            breaks.add(j)
            segment_start = j

    out: list[Segment] = []
    edges = [0, *sorted(breaks), len(text)]
    for a, b in pairwise(edges):
        raw = text[a:b]
        stripped = raw.strip()
        if not stripped:
            continue
        start = a + raw.index(stripped)
        out.append(Segment(start, start + len(stripped), stripped, _is_heading(stripped)))
    return out
