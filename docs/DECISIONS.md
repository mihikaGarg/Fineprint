# Decisions

One line each: date, decision, why.

- 2026-11-06 — Python packages live at the repo root (`contracts/`, `shared/`, `compiler/`, `enforce/`) in one uv project — simplest imports for a hackathon; split later if needed.
- 2026-11-06 — Bumped SCHEMA_VERSION to 0.2.0 for Expense/Ruleset/Trace models; enforce engine filters rule applicability by category/budget line before evaluation — prevents cross-category budget pollution while maintaining pure deterministic <10ms execution.
- 2026-11-06 — Built compiler citation verification and FastAPI bridge (port 8000) with Live Compliance Studio in web UI — connects PDF uploads and live spend evaluation to Next.js with local offline fallback.
