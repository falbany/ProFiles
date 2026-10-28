# Changelog

All notable changes to ProFiles are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2026-10-28

### Breaking changes

- **Workflow hooks schema**: the overloaded `content:` step key is replaced
  by two purpose-specific keys, valid on every step type — `command:`
  (shell command template, required for `run`/`run_after`/`replace`/`check`)
  and `message:` (Markdown message, required for `notify`, optional
  elsewhere). There is **no legacy alias by design**: a `.profiles` file
  still using `content:` fails schema validation with the generic
  unknown-key error. See the "Migrating from `content:`" section in
  `docs/hooks-guide.en.md` (also available in French).
- The `{{content}}` token is removed; use `{{command}}` / `{{message}}`
  (both brace forms accepted). These resolve to the current step's
  command / message, usable in any step text including `ask:` prompts.
- `WorkflowStep` programmatic construction now raises `ValueError` on the
  same invalid combinations the schema rejects (`notify` without
  `message`, command steps without `command`).

### Added

- A `run`/`check`/`replace`/`run_after` step can now talk to the user:
  its `message:` is shown as a non-blocking notice (web UI notification;
  headless: stdout), or rendered above the `ask:` question in the same
  Yes/Skip/No dialog when both keys are present. Command execution,
  return-code/timeout/`on_failure`/`wait`/`run_after` semantics are
  unchanged.
- YAML `if:` condition keys on workflow steps are now honored (the key
  previously never reached the engine); the schema rejects unknown step
  keys.
- **Command output capture** (#7): blocking command steps
  (`run` with `wait: true`, `check`, `replace`) capture the combined
  stdout + stderr (locale-decoded, tail-bounded to ~4 KB). A new
  per-step `output: hide | show | fail_only` key controls display
  (default `hide`), the `{{output}}` token makes the most recent
  captured output referenceable from any later step text, and failing
  steps now report `Step failed (rc=<code>)` plus a `Last output:`
  block when configured to show it. Captured output is also logged as
  a `COMMAND_OUTPUT` event in profiles.log (web log viewer) and
  rendered in the web Workflow Runner below the completion banner.
  Blocking children consequently no longer stream their output into
  the ProFiles console (documented behavior change).

## [0.9.0] - 2026-10-25

Release candidate for 1.0.0. First release under Semantic Versioning
(previously calendar-versioned, last CalVer release: 2026.8.0).

### Added

- Native installers built and published from the `v*` tag pipeline:
  Windows MSI, macOS DMG, Linux `.deb` (Briefcase 0.4.x). AppImage is
  not shipped: its Briefcase backend is currently broken upstream
  (template/cookiecutter 2.7 incompatibility) and deprecated in favour
  of system packages.
- SHA256 checksums generated for every release artifact.
- Release guard validating the tag is SemVer and matches
  `[project].version`.
- `*.profiles` launch-handoff document type registered by the native
  installers on every platform.

### Changed

- Version numbering migrated from CalVer (`2026.8.0`) to SemVer;
  `0.9.0` is the release candidate of `1.0.0`.
- The application version is centralized on `[project].version` in
  `pyproject.toml`: Briefcase inherits it via PEP 621 metadata, the web
  UI receives it at build time, and CI enforces lockfile consistency
  (`uv sync --locked`).
- The web (React) front-end is the default UI; the Tkinter front-end is
  deprecated and kept for developer use only.

### Fixed

- `profiles.__version__` resolution prefers the canonical distribution
  name (`profiles-app`) so stale legacy metadata can no longer shadow
  the installed version.
- Web header version fallback is injected at build time instead of a
  hardcoded string.
- Release workflow hardening: single fan-in release job (no concurrent
  release creation, no partial releases on platform failure),
  unattended packaging (`--no-input`), per-platform interpreter pinning,
  and linuxdeploy downloaded on demand.
