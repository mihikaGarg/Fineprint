# Decisions

One line each: date, decision, why.

- 2026-11-06 — Python packages live at the repo root (`contracts/`, `shared/`, `compiler/`, `enforce/`) in one uv project — simplest imports for a hackathon; split later if needed.
- 2026-11-06 — Bumped SCHEMA_VERSION to 0.2.0 for Expense/Ruleset/Trace models; enforce engine filters rule applicability by category/budget line before evaluation — prevents cross-category budget pollution while maintaining pure deterministic <10ms execution.
- 2026-11-06 — Built compiler citation verification and FastAPI bridge (port 8000) with Live Compliance Studio in web UI — connects PDF uploads and live spend evaluation to Next.js with local offline fallback.
- 2026-11-07 — Citations require char_start/char_end matching len(quote); SCHEMA_VERSION 0.3.0 — CLAUDE.md requires every rule to carry verified offsets.
- 2026-11-07 — Rule params (dates, dollar thresholds, categories) are parsed from the cited clause; unparseable candidates are rejected, never defaulted — the old proposer hard-coded 2026 dates for any grant.
- 2026-11-07 — Sample ruleset is compiled from fixture page text by the real compiler — fixture citations are verified by construction.
- 2026-11-07 — Web studio has no client-side evaluator fallback; if the API is down it says so — a second, divergent evaluator in the UI (with a hard-coded latency) could show verdicts the engine never made.
- 2026-11-07 — threshold_approval triggers at >= threshold — clauses read "$X or more".
