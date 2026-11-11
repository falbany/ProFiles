<!--
Thank you for contributing to ProFiles! 🎉
Please fill out this template — it speeds up review considerably.
-->

## What does this PR do?

<!-- A clear description of the change. Link the issue it closes: `closes #123`. -->

## Type of change

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that changes existing behavior)
- [ ] 📝 Documentation
- [ ] 🔧 Tooling / CI / packaging
- [ ] ♻️ Refactor (no behavior change)

## Pre-commit checklist

- [ ] `ruff format` applied
- [ ] `ruff check --fix` passes
- [ ] Pylint score > 8.0 (`pylint src/profiles`)
- [ ] Tests pass (`pytest`)
- [ ] Coverage > 85% (`pytest --cov=src/profiles`)
- [ ] Type hints added for public functions
- [ ] Docstrings present for public APIs
- [ ] No TODOs left (or tracked in an issue)
- [ ] `AGENTS.md` / `tests/AGENTS.md` updated if the module tree or public imports changed

## Testing

<!-- How was this tested? Which tests were added (regression test for bug fixes)? -->

## Screenshots

<!-- Required for any UI change (web front-end / desktop). Delete otherwise. -->
