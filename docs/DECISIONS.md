# Decisions

One line each: date, decision, why.

- 2026-11-06 — Python packages live at the repo root (`contracts/`, `shared/`, `compiler/`, `enforce/`) in one uv project — simplest imports for a hackathon; split later if needed.
- 2026-11-06 — Rule IR is a closed discriminated union of 5 kinds (category_prohibition, period_of_performance, budget_line_cap, per_item_threshold, prior_approval_required) — enforce semantics stay deterministic; clauses that fit none become NEEDS_REVIEW, not new ad-hoc rules.
- 2026-11-06 — Citation offsets are 0-based half-open into the extracted text of a 1-based page, and the schema checks span length == len(quote) — cheap pre-check before the real PDF verifier.
- 2026-11-06 — Decision validates that its verdict follows from its trace (any FAIL → BLOCKED, else any ESCALATE → NEEDS_REVIEW, else ALLOWED) — a verdict can never disagree with its clause trace.
- 2026-11-06 — Expense.category is assigned before ENFORCE; None escalates — keeps classification (possibly LLM) out of the enforce path.
- 2026-11-06 — Push straight to main, no PRs or reviews — hackathon speed; make check before every commit keeps main green.
