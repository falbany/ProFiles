# Contributing to ProFiles

Thank you for wanting to contribute! 🎉 This document describes how to set up
your development environment, the quality standards we expect, and the
submission process.

> The full architecture reference is [`AGENTS.md`](AGENTS.md) — this document
> is the contribution-oriented companion guide.

## 📋 Table of Contents

1. [Development environment](#-development-environment)
2. [Contribution workflow](#-contribution-workflow)
3. [Quality standards](#-quality-standards)
4. [Testing](#-testing)
5. [Architecture in brief](#-architecture-in-brief)
6. [Reporting a bug / proposing a feature](#-reporting-a-bug--proposing-a-feature)
7. [Commits and Pull Requests](#-commits-and-pull-requests)

---

## 🛠️ Development environment

Prerequisites: **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone https://github.com/falbany/profiles.git
cd profiles

# Development install (deps + dev extras)
uv sync --locked
# or with pip:
pip install -e ".[dev]"

# Install pre-commit hooks (recommended)
pre-commit install

# …or do all of the above in one shot:
make dev
```

### Daily commands (via make)

All common tasks have a make target — run `make help` for the full list:

```bash
make dev            # One-shot setup: deps + pre-commit hooks + web deps
make run            # Run the app from source
make test           # Tests with coverage
make web-build      # Build the web front-end
make check          # Run ALL CI gates (read-only)
make pre-push       # Auto-fix, then run all gates (mutates files)
make clean          # Remove caches (keeps .venv); make clean-all also removes it
```

Or with uv directly:

```bash
uv run ruff format .          # Format
uv run ruff check --fix .     # Lint + auto-fix
uv run pylint src/profiles    # Static analysis (score ≥ 8.0 required)
uv run pyright src/profiles   # Type checking (0 errors expected)
uv run pytest                 # Tests
```

### Web front-end (`src/profiles/web`)

The default front-end is a React PWA + Vite + TypeScript served by the local
FastAPI server:

```bash
make web-install   # npm install
make web-build     # regenerates dist/ (served by profiles.server.static)
make web-test      # vitest
# equivalent to: cd src/profiles/web && npm install / run build / run test
```

> ⚠️ `src/profiles/web/dist/` is committed: after a build, include the
> regenerated assets in your commit.

---

## 🔄 Contribution workflow

1. **Open or comment on an issue** before any non-trivial change — it avoids
   duplicated work.
2. **Create a dedicated branch** from `main`:

   ```bash
   git checkout -b fix/my-fix     # or feat/my-feature
   ```

   One branch = one topic. Don't mix fixes and features.
3. **Develop** following the standards below.
4. **Verify locally** before pushing:

   ```bash
   make check        # all CI gates, read-only
   # or individually:
   pre-commit run --all-files
   uv run ruff format --check .
   uv run ruff check .
   uv run pylint src/profiles --fail-under=8.0
   uv run pytest --cov=src/profiles --cov-fail-under=85
   ```

5. **Push and open a Pull Request** against `main`. CI (Ruff format, Ruff
   lint, Pylint ≥ 8.0, pytest with coverage ≥ 85 %) must pass.

### Project preferences

- Use **uv** and `uv.lock` (CI workflows use `astral-sh/setup-uv`).
- New Python imports go through `profiles.core` (public surface) or its
  sub-packages — see [`AGENTS.md`](AGENTS.md) for the verified import list.
- Don't hand-edit generated files (e.g. `_version.py`).

---

## ✅ Quality standards

Full details and examples in [`AGENTS.md`](AGENTS.md). Summary:

| Rule             | Expectation                                                         |
| ---------------- | ------------------------------------------------------------------- |
| **SOLID / SRP**  | One class/method = one responsibility                               |
| **DRY**          | No duplicated logic (parsing, config, etc. are centralized)         |
| **KISS**         | Minimal complexity; cyclomatic complexity < 15                      |
| **Type hints**   | On all public functions                                             |
| **Docstrings**   | On all public APIs                                                  |
| **Functions**    | < 50 lines; prefer pure functions and immutability                  |
| **Errors**       | Fail fast, explicit messages, never silent failures                 |
| **Naming**       | PascalCase classes, snake_case functions/variables, UPPER_CASE constants |

### Layer boundaries (non-negotiable)

- `profiles.core`: **zero** UI imports (FastAPI, React, pywebview).
- `profiles.web` / `profiles.server` / `profiles.desktop`: delegate all
  business logic to the core.
- `profiles.utils`: pure, stateless, domain-agnostic helpers.

## 🧪 Testing

- Framework: **pytest** (+ pytest-mock, pytest-cov). Front-end: **vitest**.
- One test = one thing, deterministic, self-documenting
  (*Given / When / Then* style in the docstring).
- Reusable fixtures in `conftest.py`; the test tree is documented in
  [`tests/AGENTS.md`](tests/AGENTS.md).
- **Every bug fix comes with a regression test**; every new feature ships
  with its unit tests.
- Coverage target: **> 85 %** (`uv run pytest --cov=src/profiles`).

## 🏗️ Architecture in brief

```
src/profiles/
├── core/        # Pure business logic (config, processing, environment, telemetry)
├── launch/      # Launch-time resolution (pure logic)
├── server/      # Local FastAPI server (web front-end backend)
├── web/         # React PWA + Vite + TS front-end (dist/ committed)
├── desktop/     # PyWebView shell (native windowing)
├── utils/       # Stateless, framework-agnostic helpers
└── app.py       # Entry point (web/desktop backend or headless CLI)
```

Any module creation/move must update the tree in [`AGENTS.md`](AGENTS.md)
**and** [`tests/AGENTS.md`](tests/AGENTS.md) in the same commit.

### Versioning

The version is derived from **git tags** via hatch-vcs: no manual version
bumps. To trigger a release, the maintainer pushes a `v*` tag.

---

## 🐛 Reporting a bug / proposing a feature

Please use the GitHub issue templates (they appear when you
[open a new issue](https://github.com/falbany/profiles/issues/new/choose)).

**Bug** — include:

- ProFiles version and OS (Windows / macOS / Linux);
- Minimal reproduction steps;
- Expected vs. actual behavior;
- Relevant `.profiles.yaml` / log excerpts (sanitized).

**Feature** — start with a discussion issue covering:

1. The problem to solve (not the solution);
2. Concrete evidence/use cases;
3. A proposed approach and the alternatives considered.

Documentation contributions in both English and French are welcome
(`docs/`, `README.md` / `README.fr.md`).

## 📝 Commits and Pull Requests

- Commit messages in **Conventional Commits** style:
  `fix(config): ...`, `feat(web): ...`, `docs: ...`, `refactor(core): ...`.
- PRs: clear title, description of the change, linked issue
  (`closes #123`), screenshot for any UI change.
- PRs are reviewed by the maintainer; please be responsive to feedback.
- A green CI is required before merge.

---

## 📜 License

By contributing, you agree that your contributions will be licensed under
the project's [MIT license](LICENCE).
