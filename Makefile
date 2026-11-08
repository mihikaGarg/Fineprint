.PHONY: install check lint format typecheck test api web report report-dry report-replay demo playground

install:
	uv sync

check: lint typecheck test

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run pyright

test:
	uv run pytest

api:
	uv run uvicorn api.main:app --reload --port 8000

web:
	npm --prefix web run dev

report:
	uv run python -m compiler.report --mode keyword

report-dry:
	uv run python -m compiler.report --mode dry-run

report-replay:
	uv run python -m compiler.report --mode replay --replay fixtures/llm_replays/sample_grant.json

demo:
	uv run python scripts/demo_walkthrough.py

# Test page at http://localhost:8000/playground, never uses an API key.
playground:
	env -u ANTHROPIC_API_KEY FINEPRINT_PROPOSER=keyword uv run uvicorn api.main:app --port 8000
