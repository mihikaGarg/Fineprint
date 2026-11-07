.PHONY: install check lint format typecheck test api web

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
