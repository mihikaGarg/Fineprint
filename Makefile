.PHONY: install check lint format typecheck test

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
