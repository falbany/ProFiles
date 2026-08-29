.PHONY: install test lint format typecheck clean poetry-install poetry-test poetry-lint poetry-format

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

poetry-install:
	poetry install

poetry-test:
	poetry run pytest --cov

poetry-lint:
	poetry run ruff check --fix .

poetry-format:
	poetry run ruff format .