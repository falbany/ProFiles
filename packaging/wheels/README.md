# Vendored wheels

## proxy_tools-0.1.0-py3-none-any.whl

**Why vendored:** `pywebview` (all versions) depends on `proxy_tools`,
but `proxy-tools` on PyPI ships only an sdist (`proxy_tools-0.1.0.tar.gz`,
unreleased since 2019). Briefcase installs macOS bundle requirements with
`pip --only-binary :all:` (see `briefcase/platforms/macOS/__init__.py`,
"Consistency + Security" rationale), so an sdist-only transitive dep makes
the whole requirement set unresolvable
(`ResolutionImpossible: proxy-tools`).

**Provenance:** built from the official PyPI sdist with:

```bash
uvx pip wheel proxy-tools==0.1.0 --no-deps -w packaging/wheels/
```

Pure-Python universal wheel (`py3-none-any`) — satisfies Briefcase's
macOS two-arch install passes (arm64 + x86_64) and is unaffected by
`--only-binary`, which filters index lookups only.

**Remove when:** `proxy-tools` publishes a wheel on PyPI (then drop the
local-path entry from `[tool.briefcase.app.profiles] requires`).

**Verify after rebuild:**

```bash
uvx pip hash packaging/wheels/proxy_tools-0.1.0-py3-none-any.whl
```
