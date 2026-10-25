# Changelog

All notable changes to ProFiles are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] - 2026-10-25

Release candidate for 1.0.0. First release under Semantic Versioning
(previously calendar-versioned, last CalVer release: 2026.8.0).

### Added

- Native installers built and published from the `v*` tag pipeline:
  Windows MSI, macOS DMG, Linux `.deb` and AppImage (Briefcase 0.4.x).
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
