# ============================================
# ProFiles Makefile
# ============================================
# Canonical toolchain: uv (hatchling backend).
# `make help` lists all targets.

# Variables
UV := uv
PYTHON := $(UV) run python
PYTEST := $(UV) run pytest
PYLINT := $(UV) run pylint
RUFF := $(UV) run ruff
PYRIGHT := $(UV) run pyright
BRIEFCASE := $(UV) run briefcase

WEB_DIR := src/profiles/web

# ============================================
# Installation & Setup
# ============================================
.PHONY: install dev setup install-system install-system-dev uninstall

install: ## Install dependencies with uv (locked)
	@echo "📦 Installing ProFiles with uv..."
	$(UV) sync --locked
	@echo "✅ Installation complete!"

dev: ## Full development setup (deps + hooks + web)
	@echo "🚀 Setting up full development environment..."
	$(MAKE) install
	$(MAKE) install-hooks
	$(MAKE) web-install
	@echo "✅ Development environment ready!"

setup: ## Alias for dev
	$(MAKE) dev

install-system: ## Install system-wide (standard mode)
	@echo "📦 Installing ProFiles system-wide (standard mode)..."
	pip install .
	@echo "✅ System installation complete!"

install-system-dev: ## Install system-wide (development mode)
	@echo "📦 Installing ProFiles system-wide (development mode)..."
	pip install -e ".[dev]"
	@echo "✅ Development installation complete!"

uninstall: ## Uninstall ProFiles system-wide installation
	@echo "🗑️  Uninstalling ProFiles..."
	pip uninstall -y profiles-app
	@echo "✅ Uninstallation complete!"

install-hooks: ## Install pre-commit hooks
	@echo "🪝 Installing pre-commit hooks..."
	$(UV) run pre-commit install --allow-missing-config
	@echo "✅ Pre-commit hooks installed!"

# ============================================
# Running
# ============================================
.PHONY: run run-desktop run-cli

run: ## Run the app from source (desktop backend)
	@echo "▶️  Running ProFiles from source..."
	$(PYTHON) -m profiles.app

run-cli: ## Run the app from source (headless CLI mode)
	@echo "▶️  Running ProFiles headless..."
	$(PYTHON) -m profiles.app --headless

run-desktop: ## Alias for run
	$(MAKE) run

# ============================================
# Testing
# ============================================
.PHONY: test test-verbose test-report web-install web-build web-test

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

web-install: ## Install web front-end dependencies (npm)
	@echo "📦 Installing web front-end dependencies..."
	cd $(WEB_DIR) && npm install
	@echo "✅ Web dependencies installed!"

web-build: ## Build the web front-end (dist/ is committed — include it in your commit)
	@echo "🔨 Building web front-end..."
	cd $(WEB_DIR) && npm run build
	@echo "✅ Web build complete!"
	@echo "⚠️  src/profiles/web/dist/ is committed: include the regenerated assets in your commit."

web-test: ## Run web front-end tests (vitest)
	@echo "🧪 Running web front-end tests..."
	cd $(WEB_DIR) && npm run test
	@echo "✅ Web tests complete!"

# ============================================
# Quality Checks
# ============================================
.PHONY: lint lint-check format format-check typecheck pylint check

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
	$(PYRIGHT) src/profiles
	@echo "✅ Type checking complete!"

pylint: ## Run pylint analysis (score ≥ 8.0 required)
	@echo "🔍 Running pylint analysis..."
	$(PYLINT) src/profiles --fail-under=8.0
	@echo "✅ Pylint analysis complete!"

check: ## Run all CI gates (read-only: format, lint, pylint, pyright, tests)
	@echo "🔒 Running all CI gates..."
	$(RUFF) format --check .
	$(RUFF) check .
	$(PYLINT) src/profiles --fail-under=8.0
	$(PYRIGHT) src/profiles
	$(PYTEST) --cov --cov-fail-under=85
	@echo "✅ All checks passed!"

# ============================================
# Pre-commit & Push (convenience wrappers)
# ============================================
.PHONY: pre-commit pre-push

pre-commit: ## Run all pre-commit checks (same as `make check`)
	$(MAKE) check

pre-push: ## Auto-fix, then run all gates (mutates files!)
	@echo "🔒 Running comprehensive pre-push checks..."
	$(RUFF) check --fix .
	$(RUFF) format .
	$(MAKE) check
	@echo "✅ All pre-push checks passed! Ready to push."

# ============================================
# Cleanup
# ============================================
.PHONY: clean clean-cov clean-all

clean: ## Remove caches and coverage artifacts (keeps .venv)
	@echo "🧹 Cleaning caches..."
	rm -rf __pycache__ .pytest_cache .mypy_cache htmlcov coverage.xml .ruff_cache .ty_cache .coverage
	find src -type d -name __pycache__ -exec rm -rf {} +
	@echo "✅ Cleanup complete!"

clean-cov: ## Remove coverage reports
	@echo "🧹 Removing coverage reports..."
	rm -rf htmlcov coverage.xml .coverage
	@echo "✅ Coverage reports removed!"

clean-all: ## Clean everything including the virtual environment
	@echo "🧹 Cleaning everything (including .venv)..."
	$(MAKE) clean
	rm -rf .venv
	@echo "✅ Everything cleaned!"

# ============================================
# Briefcase Native Installer
# ============================================
.PHONY: briefcase-dev briefcase-build briefcase-run briefcase-package briefcase-package-windows briefcase-package-macos briefcase-package-linux-deb briefcase-package-local briefcase-clean

briefcase-dev: ## Run the app from source via Briefcase
	@echo "🚀 Running ProFiles in dev mode (Briefcase)..."
	$(BRIEFCASE) dev

briefcase-build: ## Build the platform-native Briefcase app bundle
	@echo "🔨 Building native bundle via Briefcase..."
	$(BRIEFCASE) build

briefcase-run: ## Run the built Briefcase app bundle
	@echo "▶️  Running Briefcase-built bundle..."
	$(BRIEFCASE) run

briefcase-package: ## Package the native installer (.msi / .dmg / .deb)
	@echo "📦 Packaging native installer via Briefcase..."
	$(BRIEFCASE) package

briefcase-clean: ## Remove Briefcase build artifacts
	@echo "🧹 Cleaning Briefcase artifacts..."
	rm -rf build dist
	@echo "✅ Briefcase artifacts removed!"

# Host detection for local packaging dispatch (Briefcase cannot cross-compile)
ifeq ($(OS),Windows_NT)
    HOST_PKG := briefcase-package-windows
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S),Darwin)
        HOST_PKG := briefcase-package-macos
    else
        HOST_PKG := briefcase-package-linux-deb
    endif
endif

briefcase-package-windows: ## Package the Windows installer (.msi) — Windows host only
	@echo "📦 Packaging Windows MSI (requires Windows host)..."
	$(BRIEFCASE) package windows -p msi
	@echo "✅ Installer written to dist/"

briefcase-package-macos: ## Package the macOS disk image (.dmg) — macOS host only
	@echo "📦 Packaging macOS DMG (requires macOS host)..."
	$(BRIEFCASE) package macos -p dmg
	@echo "✅ Installer written to dist/"

briefcase-package-linux-deb: ## Package the Linux .deb — Linux host only
	@echo "📦 Packaging Linux .deb (requires Linux host)..."
	$(BRIEFCASE) package linux -p deb
	@echo "✅ Package written to dist/"

briefcase-package-local: ## Package for the current host OS (auto-detect)
	@echo "📦 Detected host package target: $(HOST_PKG)"
	$(MAKE) $(HOST_PKG)

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
# Help
# ============================================
.PHONY: help

help: ## Show all available commands
	@echo "============================================"
	@echo "  ProFiles Makefile - Available Commands"
	@echo "============================================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-26s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "============================================"

.DEFAULT_GOAL := help
