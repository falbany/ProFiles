# Design — hatch-vcs tag-derived versioning

Date: 2026-11-05 · Status: awaiting approval · Size: small change

## Intent & why

Kill the general versioning pain: the manual version-bump edit in
`pyproject.toml`, the tag↔pyproject drift risk (currently defended by a CI
guard), the `0.0.0-dev` fallback ambiguity, and the stale-egg-info shadowing
bug class. Adopt **hatch-vcs**: the git tag becomes the single source of
truth, every build self-describes its exact commit, and the release flow
(manual tag push → pipeline) is unchanged by decision of the maintainer.

## Goals

- `git tag v0.12.0 && git push origin v0.12.0` is the only release act; zero
  file edits per release.
- Non-tag builds report PEP 440 lineage versions, e.g.
  `0.11.0rc2.post3+g791f581` (scheme configurable), `+dirty` when the tree is.
- Installed copies and diagnostics logs carry exact provenance.

## Non-goals

- No Commitizen / conventional-commit tag automation (explicitly declined for
  now; layerable later).
- No change to the tag naming convention (`vMAJOR.MINOR.PATCH[-pre]` stays).
- No PyPI publishing pipeline change (if publishing ever happens, add
  `local-scheme = "no-local-version"` then).

## Constraints

- Build backend stays hatchling; existing `[tool.hatch.build.hooks.custom]`
  (web dist) must keep working — build hooks compose.
- Briefcase merges PEP 621 metadata; it reads the resolved version at build
  time. Release installers are built on tag checkouts → clean version.
- `release.yml` currently guards tag↔pyproject equality; that check becomes
  tautological and is removed. The SemVer-format check on the tag stays.

## Approach

**Chosen**: hatch-vcs (hatchling-native wrapper of setuptools-scm). Rejected
alternatives: GitVersion (branch-model tool, external binary, wrong ecosystem
for a trunk-based Python repo); setuptools-scm directly (would drag in a
setuptools frontend); uv-dynamic-versioning (extra plugin for no gain);
static version + `uv version`/Commitizen (keeps the two-artifact drift
surface we are trying to delete).

Config lives entirely in `pyproject.toml` — no dedicated file:

```toml
[build-system]
requires = ["hatchling", "hatch-vcs", "nodeenv>=1.8.0"]

[project]
name = "profiles-app"
dynamic = ["version"]

[tool.hatch.version]
source = "vcs"

[tool.hatch.build.hooks.vcs]
version-file = "src/profiles/_version.py"
```

## Touch points

1. `pyproject.toml` — `version = "..."` → `dynamic = ["version"]` + the two
   `[tool.hatch.*]` tables above.
2. `.gitignore` — add `src/profiles/_version.py` (generated at build time).
3. `src/profiles/__init__.py` — `_resolve_version()` keeps
   `importlib.metadata` as primary; the pyproject-regex fallback is replaced
   by importing the generated `profiles._version` (guarded); `0.0.0-dev`
   stays as last resort for git-less source trees without a built hook.
4. `.github/workflows/release.yml` — drop the tag↔pyproject match check from
   the guard job (keep the SemVer-format check); add `fetch-depth: 0` to
   **every** build job checkout so the tag is visible at build time (classic
   hatch-vcs CI trap — without it artifacts silently build a fallback
   version). Same for any other workflow that builds the package.
5. `tests/test_app.py` — `_canonical_version()` reads `pyproject["project"]
   ["version"]`, which no longer exists. Rewrite: assert `profiles.__version__`
   is a valid PEP 440 string and matches the generated `_version.py` when
   present. `tests/core/config/test_models.py` consumes `__version__`
   dynamically — no change.
6. `src/profiles/core/config/models.py`, `desktop/lifecycle.py`,
   `server/routes/instance.py` — read `__version__` only; no change.

## Verification

- `uv sync` then `python -c "import profiles; print(profiles.__version__)"`
  in a clean clone → lineage version derived from the last tag.
- Editable reinstall per commit updates the version (stale-metadata bug gone).
- CI green on a PR touching this; release flow exercised on the next real
  tag (manual push, as decided).

## Left to the builder

- Exact `version_scheme` (default `guess-next-dev`) — default is fine unless
  review says otherwise.
- Whether other workflows (`build-windows.yml`) check out shallow and build
  the package — audit and apply `fetch-depth: 0` as needed.
