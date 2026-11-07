"""Compile inspector: run the compile pipeline and write an HTML report.

    python -m compiler.report                         # sample grant, keyword proposer
    python -m compiler.report --mode dry-run          # show the exact Claude request, send nothing
    python -m compiler.report --mode replay --replay fixtures/llm_replays/sample_grant.json
    python -m compiler.report --pdf grant.pdf --mode llm   # real API call (needs ANTHROPIC_API_KEY)

Replay feeds a saved "model answer" through the real verification steps without
calling the API, so you can see what gets accepted or rejected and why.
Replayed answers are never written to the LLM cache.
"""

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path
from typing import Any, Literal

from compiler.extractor import extract_pdf_pages
from compiler.llm_propose import RULES_SCHEMA, SYSTEM_PROMPT, build_prompt, make_llm_proposer
from compiler.pipeline import compile_pages
from contracts.models import Ruleset
from shared.llm import LLMRequest, LLMResponse, Transport, is_configured

Mode = Literal["keyword", "replay", "dry-run", "llm"]

# Rough planning numbers for the dry-run estimate (Claude Opus 5.5 list price).
INPUT_USD_PER_MTOK = 4
OUTPUT_USD_PER_MTOK = 20
ASSUMED_OUTPUT_TOKENS = 4_000


def replay_transport(path: Path) -> Transport:
    text = path.read_text(encoding="utf-8")

    def transport(request: LLMRequest) -> LLMResponse:
        return LLMResponse(text=text, model="replay", input_tokens=0, output_tokens=0)

    return transport


def _highlight(text: str, spans: list[tuple[int, int, str]]) -> str:
    """Escape page text and wrap verified citation spans in <mark>."""
    out: list[str] = []
    pos = 0
    for start, end, label in sorted(spans):
        if start < pos:  # overlapping citation; already highlighted
            continue
        out.append(html.escape(text[pos:start]))
        out.append(f'<mark title="{html.escape(label)}">{html.escape(text[start:end])}</mark>')
        pos = end
    out.append(html.escape(text[pos:]))
    return "".join(out)


def build_report(
    *,
    title: str,
    mode: Mode,
    pages: dict[int, str],
    ruleset: Ruleset | None,
    rejected: list[dict[str, Any]],
    request: LLMRequest,
) -> str:
    e = html.escape
    verified = ruleset.rules if ruleset else []
    proposed = len(verified) + len(rejected)

    rule_rows = "".join(
        f"<tr><td><code>{e(r.id)}</code></td><td>{e(r.rule_type)}</td>"
        f"<td><pre>{e(json.dumps(r.params, indent=1))}</pre></td>"
        f"<td>p. {r.citation.page} [{r.citation.char_start}:{r.citation.char_end}]</td>"
        f"<td class=q>{e(r.citation.quote)}</td></tr>"
        for r in verified
    )
    rejected_rows = "".join(
        f"<tr><td class=bad>{e(str(x.get('reason', '')))}</td>"
        f"<td>{e(str(x.get('candidate', {}).get('rule_type', '')))}</td>"
        f"<td>p. {e(str(x.get('candidate', {}).get('page', '')))}</td>"
        f"<td class=q>{e(str(x.get('candidate', {}).get('quote', '')))}</td></tr>"
        for x in rejected
    )

    spans: dict[int, list[tuple[int, int, str]]] = {}
    for r in verified:
        c = r.citation
        spans.setdefault(c.page, []).append((c.char_start, c.char_end, f"{r.id} {r.rule_type}"))
    page_blocks = "".join(
        f"<section class=page><h3>Page {n}</h3><div class=text>"
        f"{_highlight(text, spans.get(n, []))}</div></section>"
        for n, text in sorted(pages.items())
    )

    input_tokens = (len(request.system) + len(request.prompt)) // 4
    est_usd = (
        input_tokens * INPUT_USD_PER_MTOK + ASSUMED_OUTPUT_TOKENS * OUTPUT_USD_PER_MTOK
    ) / 1_000_000

    if mode == "dry-run":
        results = (
            "<p class=note>Dry run: nothing was sent to Claude. Below is exactly what "
            "<code>--mode llm</code> would send.</p>"
        )
    else:
        results = f"""
<h2>Verified rules ({len(verified)})</h2>
<table><tr><th>Id</th><th>Type</th><th>Params (parsed by code)</th><th>Citation</th>
<th>Quote</th></tr>{rule_rows or "<tr><td colspan=5>None</td></tr>"}</table>
<h2>Rejected ({len(rejected)})</h2>
<table><tr><th>Reason</th><th>Type</th><th>Page</th><th>Quote proposed</th></tr>
{rejected_rows or "<tr><td colspan=4>None</td></tr>"}</table>"""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compile report</title>
<style>
:root {{ --bg:#f7f4ec; --card:#fffdf7; --ink:#16181d; --muted:#5b5f68; --rule:#ddd6c6;
  --mark:#f6e27a; --ok:#1f7a4d; --bad:#b42318; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#121317; --card:#1b1d22; --ink:#ecebe6;
  --muted:#a2a5ad; --rule:#2e3138; --mark:#6b5c12; --ok:#5fd39a; --bad:#ff8a7a; }} }}
body {{ margin:0; padding:24px 16px; background:var(--bg); color:var(--ink);
  font:15px/1.5 system-ui, sans-serif; }}
main {{ max-width:1100px; margin:auto; }}
h1 {{ font-family:Georgia, serif; font-weight:400; margin:0 0 4px; }}
h2 {{ font-family:Georgia, serif; font-weight:400; margin-top:32px; }}
.meta {{ color:var(--muted); font-size:13px; }}
.stats {{ display:flex; gap:12px; flex-wrap:wrap; margin:16px 0; }}
.stat {{ background:var(--card); border:1px solid var(--rule); border-radius:10px;
  padding:10px 14px; min-width:110px; }}
.stat b {{ display:block; font-size:22px; }}
table {{ width:100%; border-collapse:collapse; background:var(--card); font-size:13px; }}
th, td {{ border:1px solid var(--rule); padding:6px 8px; text-align:left; vertical-align:top; }}
pre {{ margin:0; white-space:pre-wrap; font-size:12px; }}
.q {{ font-family:Georgia, serif; }}
.bad {{ color:var(--bad); }}
.ok {{ color:var(--ok); }}
.note {{ background:var(--card); border-left:3px solid var(--ok); padding:8px 12px; }}
.page {{ background:var(--card); border:1px solid var(--rule); border-radius:10px;
  padding:12px 16px; margin:12px 0; }}
.page h3 {{ margin:0 0 6px; font-size:13px; color:var(--muted); }}
.text {{ white-space:pre-wrap; font-family:Georgia, serif; }}
mark {{ background:var(--mark); color:inherit; }}
details {{ background:var(--card); border:1px solid var(--rule); border-radius:10px;
  padding:8px 12px; margin:8px 0; }}
summary {{ cursor:pointer; }}
.wrap {{ overflow-x:auto; }}
</style></head><body><main>
<h1>Compile report</h1>
<div class=meta>{e(title)} · mode: <b>{e(mode)}</b> · model: {e(request.model)}
 · effort: {e(request.effort)}</div>
<div class=stats>
<div class=stat>Pages<b>{len(pages)}</b></div>
<div class=stat>Proposed<b>{proposed if mode != "dry-run" else "&ndash;"}</b></div>
<div class="stat ok">Verified<b>{len(verified) if mode != "dry-run" else "&ndash;"}</b></div>
<div class="stat bad">Rejected<b>{len(rejected) if mode != "dry-run" else "&ndash;"}</b></div>
<div class=stat>Est. LLM cost<b>${est_usd:.2f}</b></div>
</div>
<div class=wrap>{results}</div>
<h2>Pages (verified citations highlighted)</h2>
{page_blocks}
<h2>Claude request</h2>
<p class=meta>~{input_tokens:,} input tokens (estimated as characters ÷ 4). Cost estimate assumes
{ASSUMED_OUTPUT_TOKENS:,} output tokens at Opus 5.5 list price. Cache key
<code>{request.cache_key()[:12]}</code>: rerunning the same request is free.</p>
<details><summary>System prompt</summary><pre>{e(request.system)}</pre></details>
<details><summary>User prompt (document)</summary><pre>{e(request.prompt)}</pre></details>
<details><summary>Output schema</summary><pre>{e(json.dumps(request.schema, indent=2))}</pre>
</details>
</main></body></html>
"""


def run(
    mode: Mode,
    pages: dict[int, str],
    title: str,
    replay: Path | None = None,
) -> str:
    grant_id = (
        "grant_" + hashlib.sha256(json.dumps(pages, sort_keys=True).encode()).hexdigest()[:12]
    )
    request = LLMRequest(system=SYSTEM_PROMPT, prompt=build_prompt(pages), schema=RULES_SCHEMA)
    ruleset: Ruleset | None = None
    rejected: list[dict[str, Any]] = []

    if mode == "keyword":
        ruleset, rejected = compile_pages(pages, grant_id, title)
    elif mode == "replay":
        if replay is None:
            raise SystemExit("--mode replay needs --replay FILE")
        proposer = make_llm_proposer(replay_transport(replay), cache=False)
        ruleset, rejected = compile_pages(pages, grant_id, title, proposer)
    elif mode == "llm":
        if not is_configured():
            raise SystemExit("ANTHROPIC_API_KEY is not set; use --mode dry-run or replay instead")
        ruleset, rejected = compile_pages(pages, grant_id, title, make_llm_proposer())

    return build_report(
        title=title, mode=mode, pages=pages, ruleset=ruleset, rejected=rejected, request=request
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--pdf", type=Path, help="Grant PDF (default: bundled sample grant)")
    parser.add_argument(
        "--mode", choices=["keyword", "replay", "dry-run", "llm"], default="keyword"
    )
    parser.add_argument("--replay", type=Path, help="JSON model answer for --mode replay")
    parser.add_argument("-o", "--out", type=Path, default=Path("reports/compile-report.html"))
    args = parser.parse_args(argv)

    if args.pdf:
        pages = {p.page_number: p.raw_text for p in extract_pdf_pages(args.pdf.read_bytes())}
        title = args.pdf.name
    else:
        from fixtures.sample_data import SAMPLE_GRANT_NAME, SAMPLE_PAGES

        pages, title = SAMPLE_PAGES, SAMPLE_GRANT_NAME

    report = run(args.mode, pages, title, args.replay)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"Wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
