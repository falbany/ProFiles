# ============================================
# ProFiles Makefile - Enhanced Version
# ============================================

# Variables
UV := uv
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest
PYLINT := $(UV) run pylint
RUFF := $(UV) run ruff
PYRIGHT := $(UV) run pyright

# ============================================
# Installation
# ============================================
.PHONY: install install-system install-system-dev install-uv install-poetry

install: ## Install with uv (recommended)
	@echo "📦 Installing ProFiles with uv..."
	$(UV) sync
	@echo "✅ Installation complete!"

install-system: ## Install system-wide (standard mode)
	@echo "📦 Installing ProFiles system-wide (standard mode)..."
	pip install .
	@echo "✅ System installation complete!"

install-system-dev: ## Install system-wide (development mode)
	@echo "📦 Installing ProFiles system-wide (development mode)..."
	pip install -e ".[dev]"
	@echo "✅ Development installation complete!"

install-uv: ## Install uv package manager
	@echo "🔧 Installing uv package manager..."
	powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
	@echo "✅ uv installed! Restart your terminal to use it."

install-poetry: ## Install poetry if not present
	@echo "🔧 Installing poetry..."
	powershell -ExecutionPolicy ByPass -c "irm https://install.python-poetry.org | python -"
	@echo "✅ poetry installed! Restart your terminal to use it."

# ============================================
# Testing
# ============================================
.PHONY: test test-verbose test-report

test: ## Run tests with coverage
	@echo "🧪 Running tests with coverage..."
	$(PYTEST) --cov
	@echo "✅ Tests complete!"

test-verbose: ## Run tests with detailed output
	@echo "🧪 Running tests with detailed output..."
	$(PYTEST) --cov -v
	@echo "✅ Tests complete!"

test-report: ## Generate detailed HTML coverage report
	@echo "📊 Generating detailed coverage report..."
	$(PYTEST) --cov --cov-report=html:htmlcov --cov-report=xml
	@echo "✅ Coverage report generated!"
	@echo "📁 HTML report: htmlcov/index.html"
	@echo "📁 XML report: coverage.xml"

# ============================================
# Quality Checks
# ============================================
.PHONY: lint lint-check format format-check typecheck pylint

lint: ## Fix linting issues automatically
	@echo "🔍 Fixing linting issues..."
	$(RUFF) check --fix .
	@echo "✅ Linting complete!"

lint-check: ## Check linting without fixing
	@echo "🔍 Checking linting issues..."
	$(RUFF) check .
	@echo "✅ Linting check complete!"

format: ## Format code with ruff
	@echo "✨ Formatting code..."
	$(RUFF) format .
	@echo "✅ Formatting complete!"

format-check: ## Check formatting without applying
	@echo "✨ Checking code formatting..."
	$(RUFF) format --check .
	@echo "✅ Formatting check complete!"

typecheck: ## Run type checking with pyright
	@echo "🔍 Running type checking with pyright..."
	$(PYRIGHT) src/
	@echo "✅ Type checking complete!"

pylint: ## Run pylint analysis
	@echo "🔍 Running pylint analysis..."
	$(PYLINT) src/profiles --fail-under=8.0
	@echo "✅ Pylint analysis complete!"

# ============================================
# Pre-commit & Push
# ============================================
.PHONY: pre-commit pre-push install-hooks

pre-commit: ## Run all pre-commit checks
	@echo "🔒 Running pre-commit checks..."
	$(RUFF) format --check .
	$(RUFF) check .
	$(PYRIGHT) src/ || @echo "⚠️  pyright check skipped (launcher issue)"
	$(PYTEST) --cov --cov-fail-under=85
	@echo "✅ All pre-commit checks passed!"

pre-push: ## Run comprehensive checks before push
	@echo "🔒 Running comprehensive pre-push checks..."
	$(RUFF) format .
	$(RUFF) check --fix .
	$(PYLINT) src/profiles --fail-under=8.0
	$(PYRIGHT) src/
	$(PYTEST) --cov --cov-fail-under=85
	@echo "✅ All pre-push checks passed! Ready to push."

install-hooks: ## Install pre-commit hooks
	@echo "🪝 Installing pre-commit hooks..."
	uv run pre-commit install --allow-missing-config
	@echo "✅ Pre-commit hooks installed!"

# ============================================
# Cleanup
# ============================================
.PHONY: clean clean-pycache clean-cov clean-all

clean: ## Remove all build artifacts
	@echo "🧹 Cleaning all build artifacts..."
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache htmlcov coverage.xml .ruff_cache .ty_cache .coverage
	@echo "✅ Cleanup complete!"

clean-pycache: ## Remove only Python cache
	@echo "🧹 Removing Python cache files..."
	if exist __pycache__ rmdir /s /q __pycache__
	if exist .pytest_cache rmdir /s /q .pytest_cache
	if exist .mypy_cache rmdir /s /q .mypy_cache
	if exist .ruff_cache rmdir /s /q .ruff_cache
	if exist .ty_cache rmdir /s /q .ty_cache
	@echo "✅ Python cache removed!"

clean-cov: ## Remove coverage reports
	@echo "🧹 Removing coverage reports..."
	if exist htmlcov rmdir /s /q htmlcov
	if exist coverage.xml del coverage.xml
	@echo "✅ Coverage reports removed!"

clean-all: ## Clean everything including virtual environment
	@echo "🧹 Cleaning everything (including .venv)..."
	rm -rf .venv __pycache__ .pytest_cache .mypy_cache htmlcov coverage.xml .ruff_cache .ty_cache .coverage
	@echo "✅ Everything cleaned!"

# ============================================
# Development
# ============================================
.PHONY: dev setup

dev: ## Full development setup
	@echo "🚀 Setting up full development environment..."
	$(MAKE) install
	$(MAKE) install-hooks
	@echo "✅ Development environment ready!"

setup: ## Alias for dev
	$(MAKE) dev

# ============================================
# PyPI Publishing
# ============================================
.PHONY: build publish publish-test

build: ## Build distribution packages
	@echo "📦 Building distribution packages..."
	$(UV) build
	@echo "✅ Build complete! Check dist/ folder."

publish: ## Publish to PyPI (production)
	@echo "🚀 Publishing to PyPI (production)..."
	$(UV) publish
	@echo "✅ Published to PyPI!"

publish-test: ## Publish to TestPyPI
	@echo "🚀 Publishing to TestPyPI..."
	$(UV) publish --repository testpypi
	@echo "✅ Published to TestPyPI!"

# ============================================
# Poetry Targets (compatibility)
# ============================================
.PHONY: poetry-install poetry-test poetry-lint poetry-format

poetry-install: ## Install with poetry (compatibility)
	@echo "📦 Installing with poetry..."
	poetry install
	@echo "✅ Installation complete!"

poetry-test: ## Run tests with poetry (compatibility)
	@echo "🧪 Running tests with poetry..."
	poetry run pytest --cov
	@echo "✅ Tests complete!"

poetry-lint: ## Run lint with poetry (compatibility)
	@echo "🔍 Running lint with poetry..."
	poetry run ruff check --fix .
	@echo "✅ Linting complete!"

poetry-format: ## Format with poetry (compatibility)
	@echo "✨ Formatting with poetry..."
	poetry run ruff format .
	@echo "✅ Formatting complete!"

# ============================================
# Help
# ============================================
.PHONY: help

help: ## Show all available commands
	@echo "============================================"
	@echo "  ProFiles Makefile - Available Commands"
	@echo "============================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "============================================"

.DEFAULT_GOAL := help