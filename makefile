.PHONY: install test lint format typecheck clean

install:
	uv sync

test:
	uv run pytest --cov

lint:
	uv run ruff check --fix .

format:
	uv run ruff format .

typecheck:
	uv run mypy src/

clean:
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache