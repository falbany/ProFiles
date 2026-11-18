# Installer Art Native-Frame Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the two MSI BMPs so WiX's black text never lands on artwork, while keeping the ProFiles brand visible.

**Architecture:** Adopt the stock WiX art layout. The 493×312 background becomes a 164 px brand panel on the left plus a white text zone; the 493×58 banner becomes white for the title zone (x=0–428) plus a brand block on the right (x=429–492). Both are generated at 4× and LANCZOS-downsampled by the existing Pillow script, then committed.

**Tech Stack:** Pillow (generator, dev-side only), pytest (layout regression tests), Briefcase 0.4.7 / WiX UI (consumer).

**Spec:** `docs/superpowers/specs/2026-11-18-installer-art-native-frame-design.md`

## Global Constraints

- No changes under `src/profiles/**`.
- BMPs are committed assets at exactly 493×312 / 493×58, 24-bit RGB; never generated at build time.
- Generator stays stdlib + Pillow and **font-free** (no text rendering).
- No WiX/Briefcase template changes; art-only fix.
- Commits use explicit paths; the working tree carries unrelated `.zcode/` and `src/profiles/web/dist/` churn that must NOT be committed.
- English-only docs; `tests/AGENTS.md` needs no change (no new test file).

## Review Focus

1. **Banner title contrast** — the black page title is drawn at x≈20; the banner must be white left of x=429. Pinned by `test_banner_keeps_title_zone_clear`.
2. **Dialog text/link/checkbox contrast** — body text starts at x≈173; the background must be white right of x=169. Pinned by `test_background_keeps_text_zone_clear`.
3. **DPI crispness** — the banner is downscaled to 370×44; 4× supersampling prevents ragged logo edges. Verified visually and by the unchanged dimension tests.
4. **Half-applied fix** — banner reworked but background not (or vice versa). The two tests cover one asset each, so both must pass.
5. **Docs drift** — the 2026-11-17 spec still describes full-bleed art. Task 2 replaces that section and the plan's Task 2 text.

---

### Task 1: Rework the BMP generator and regenerate both assets

**Files:**
- Modify: `packaging/windows/generate_bmps.py`
- Modify: `img/installer_background.bmp`, `img/installer_banner.bmp` (regenerated)
- Test: `tests/packaging/test_windows_installer_assets.py`

**Interfaces:**
- Produces: `generate_background() -> Image.Image`, `generate_banner() -> Image.Image` (same public names the `main()` entry point already calls).
- Produces: module constants `SCALE = 4`, `PANEL_WIDTH = 164`, `BANNER_BRAND_X = 429`, `BANNER_BRAND_WIDTH = 64`.
- Produces: `_mark(size, radius, bar_width, bar_height, gap, pad, third_width) -> Image.Image` returning an RGBA mark at `SCALE`× resolution.

- [ ] **Step 1: Add the failing layout tests**

Append to `tests/packaging/test_windows_installer_assets.py`:

```python
def test_banner_keeps_title_zone_clear() -> None:
    """WiX draws the black banner title at x≈20; keep x<429 white."""
    path = REPO_ROOT / "img" / "installer_banner.bmp"
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        darkest = min(band[0] for band in rgb.crop((0, 0, 429, 58)).getextrema())
        edge = rgb.getpixel((428, 6))
        brand = rgb.getpixel((430, 6))
    assert darkest >= 250  # no art under the title
    assert min(edge) >= 250  # title zone reaches the brand block
    assert brand[2] > brand[0]  # indigo/violet block on the right


def test_background_keeps_text_zone_clear() -> None:
    """WiX draws body text from x≈173; keep x>169 white."""
    path = REPO_ROOT / "img" / "installer_background.bmp"
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        darkest = min(band[0] for band in rgb.crop((170, 0, 493, 312)).getextrema())
        panel = rgb.getpixel((10, 156))
        boundary = rgb.getpixel((164, 156))
    assert darkest >= 250  # no art under the text, links or checkbox
    assert panel[2] > panel[0]  # brand panel on the left
    assert min(boundary) >= 250  # panel ends at x=163
```

- [ ] **Step 2: Run the tests to verify they fail on the current art**

Run: `uv run --no-sync pytest tests/packaging/test_windows_installer_assets.py -q`
Expected: the two new tests FAIL (`assert darkest >= 250`), all existing tests pass.

- [ ] **Step 3: Rewrite the generator**

In `packaging/windows/generate_bmps.py`:

- Set `SCALE = 4`, `WHITE = (255, 255, 255)`, `PANEL_WIDTH = 164`,
  `BANNER_BRAND_X = 429`, `BANNER_BRAND_WIDTH = 64`.
- Keep `GRADIENT_LEFT`, `GRADIENT_RIGHT`, `BACKGROUND_SIZE`, `BANNER_SIZE`, `_lerp`.
- Remove `SOURCE`, `MARK_BOX`, `MARK_BARS`, `PILLS` and the cover-crop logic.
- Add `_h_gradient(size)` and `_v_gradient(size)` helpers that draw one line per
  column/row with `_lerp` (same technique as the old banner).
- Add `_mark(...)` drawing a white rounded square with three `GRADIENT_LEFT`
  bars on an RGBA layer, all dimensions multiplied by `SCALE` internally.
- `generate_background()`: `493×312` canvas filled white; paste a
  `164×312` vertical gradient at `(0, 0)`; paste a 56 px mark at
  `(54, 128)` with radius 14, bars 30×6, gap 4, pad 13, third bar 19;
  resize to `(493, 312)` with `Image.LANCZOS`.
- `generate_banner()`: `493×58` canvas filled white; paste a `64×58`
  horizontal gradient at `(429, 0)`; paste a 34 px mark at `(444, 12)`
  with radius 9, bars 18×4, gap 2, pad 8, third bar 11; resize to
  `(493, 58)` with `Image.LANCZOS`.
- Update the module docstring (native-frame zones, no source PNG) and make
  `--check` use only the script itself as the input timestamp.

- [ ] **Step 4: Regenerate and verify**

Run: `uv run --no-sync python packaging/windows/generate_bmps.py`
Run: `uv run --no-sync pytest tests/packaging/test_windows_installer_assets.py -q`
Expected: all tests PASS.

- [ ] **Step 5: Eyeball the assets**

Convert both BMPs to PNG (Pillow) and inspect them: banner left of x=429
pure white with the mark in the right block; background left panel purple
with the mark, right side pure white. Compare against the approved mock-up.

- [ ] **Step 6: Commit**

```bash
git add packaging/windows/generate_bmps.py img/installer_background.bmp img/installer_banner.bmp tests/packaging/test_windows_installer_assets.py
git commit -m "fix(installer): keep WiX text zones clear in branded art" && git show --stat
```

---

### Task 2: Sync the design docs and packaging README

**Files:**
- Modify: `docs/superpowers/specs/2026-11-17-windows-installer-polish-design.md` (§6.2)
- Modify: `docs/superpowers/plans/2026-11-18-windows-installer-polish.md` (Task 2 art description)
- Modify: `packaging/windows/README.md` (art section)
- Commit: `docs/superpowers/specs/2026-11-18-installer-art-native-frame-design.md` (already in tree)

**Interfaces:**
- Consumes: the layout values from Task 1.
- Produces: no code; keeps the committed spec truthful.

- [ ] **Step 1: Update the 2026-11-17 spec §6.2**

Replace the two-row table content with a short native-frame description
(164 px panel / white text zone; white title zone x=0–428 / brand block
x=429–492) and mark the "Open visual checkpoint" resolved: WiX renders
black text, mitigated by the text-safe zones. Link
`2026-11-18-installer-art-native-frame-design.md` as the superseding doc.

- [ ] **Step 2: Update the 2026-11-18 implementation plan Task 2**

Replace the "Art (spec §6.2, direction A)" paragraph and the Step 3 sketch
with the native-frame layout and a reference to the new spec. Keep the
rest of the task unchanged.

- [ ] **Step 3: Update the packaging README**

In "Regenerating the installer art", add that the layout follows WiX's
text-safe zones (banner title zone white, background text zone white) and
link the new spec alongside the original one.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-11-17-windows-installer-polish-design.md docs/superpowers/plans/2026-11-18-windows-installer-polish.md packaging/windows/README.md docs/superpowers/specs/2026-11-18-installer-art-native-frame-design.md
git commit -m "docs: record native-frame installer art layout" && git show --stat
```

---

### Task 3: Quality gates and PR artifact

**Files:** none (verification only).

- [ ] **Step 1: Format and lint the touched Python files**

Run: `uv run --no-sync ruff format packaging/windows/generate_bmps.py tests/packaging/test_windows_installer_assets.py`
Run: `uv run --no-sync ruff check packaging/windows/generate_bmps.py tests/packaging/test_windows_installer_assets.py`
Expected: clean. Commit any formatting fallout under `style: ruff format`.

- [ ] **Step 2: Full test suite**

Run: `uv run --no-sync pytest -q`
Expected: all tests pass (the packaging module included).

- [ ] **Step 3: Push and let CI rebuild the MSI**

Run: `git push`
Expected: `build-windows.yml` starts; the `ProFiles-windows-msi` artifact is
the final visual check on the work machine.

- [ ] **Step 4: Report**

Tell the owner the new artifact is ready and which screens to check
(progress/banner pages, welcome, finish). The PR description's visual
checkpoint can be updated once the artifact is confirmed.

## Self-Review Notes

- Spec coverage: background zones → Task 1; banner zones → Task 1; superseding docs → Task 2; verification → Task 3.
- Types/names consistent: `generate_background`, `generate_banner`, `_mark`, `SCALE`, `PANEL_WIDTH`, `BANNER_BRAND_X` used as defined.
- Review Focus lines 1–4 are pinned by Task 1 tests; line 5 by Task 2.
- No new files mean `tests/AGENTS.md` and `AGENTS.md` trees stay accurate.
