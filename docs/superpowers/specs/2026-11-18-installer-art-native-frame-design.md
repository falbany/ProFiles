# Installer Art — Native-Frame Layout (supersedes §6.2 of the 2026-11-17 spec)

- **Date:** 2026-11-18
- **Status:** Approved by owner 2026-11-18 (native-frame mock-up accepted)
- **Implements:** follow-up to [issue #183](https://github.com/falbany/ProFiles/issues/183), PR #190
- **Supersedes:** art direction in `2026-11-17-windows-installer-polish-design.md` §6.2

## Why

The first MSI artifact rendered the branded BMPs under WiX's own text:

- **Banner pages** draw the page title in black at **x ≈ 20 of 493** (control
  `X=15..20`, `W=300..330` dialog units, scaled ×493/370). The logo mark
  (x=16–42) and pills (x≥360) sat directly under it.
- **Welcome / Finish pages** draw body text, links and checkboxes in black
  from **x ≈ 173 of 493** (control `X=130..135`). The full-bleed background
  put the mark, wordmark and tagline in that same zone.

Text colour is fixed by the WiX UI theme; changing it would require
vendoring/patching the template, which §4 of the original spec rules out.

## Goal

Every wizard page is readable while keeping the ProFiles brand visible.

**Non-goals:** changing installer behaviour, config, scripts, or WiX
template; adding fonts at generation time (generator stays font-free);
touching `src/profiles/**`.

## Chosen approach — native-frame layout

Mirror the stock WiX art layout, which is designed around those text
coordinates.

### `img/installer_background.bmp` — 493×312, 24-bit

| Zone | Content |
| --- | --- |
| x = 0–163 | Vertical brand gradient (`#635BCC` → `#825ED9`), white rounded logo mark (56×56) centred in the panel |
| x = 164–492 | Plain white (`#FFFFFF`) — all dialog text, links and checkboxes land here |

Text starts at x≈173 (Welcome) / x≈180 (Finish), leaving a ≥ 9 px white
gutter after the panel.

### `img/installer_banner.bmp` — 493×58, 24-bit

The banner is reworked in the same pass — it is not left as-is. WiX
renders it inside a **370×44** control, so the 493×58 source is a 4/3
supersample: details are drawn at 493×58 but sized to stay crisp after the
downscale (and at 125–150 % DPI).

| Zone | Content |
| --- | --- |
| x = 0–428 | Plain white (`#FFFFFF`) — the page title (black) can run up to x≈420 |
| x = 429–492 | Brand gradient block with the white rounded logo mark (34×34) |

No pills or wordmark in the banner: the right block alone carries the brand.
This is the same layout rule as the stock WiX banner (content at the far
right, title zone clear), adapted to the ProFiles colours.

A full-height purple band on the left — even one matching the background
panel — is rejected: the banner title starts at x≈20, so the black text
would land on it again.

### Rejected — baked white "content card"

Keeping the full gradient and painting a white card under the text zones.
More brand colour, but the card edges must be tuned per dialog, can clash
with the native separator lines/buttons, and still constrains long titles.
More fragile for no functional gain.

## Implementation notes

- `packaging/windows/generate_bmps.py`: replace the cover-crop background and
  the left-mark banner with the zones above; keep the Pillow-only, font-free
  drawing and the `--check` flag. Regenerate and commit both BMPs.
- `tests/packaging/test_windows_installer_assets.py`: add layout regression
  guards (existing dimension tests stay):
  - banner x < 429 is near-white (black title contrast);
  - background x > 169 is near-white;
  - both files still carry brand colour in their art zone.
- Docs: update §6.2 of the 2026-11-17 spec and Task 2 of the implementation
  plan to point at this document, so the committed design stays truthful.
- Verification: regenerate, run the packaging tests, eyeball both BMPs; the
  CI MSI artifact is the final visual check on the work machine.

## Left to the builder

Exact gradient stops, mark radius/bar proportions, and the pixel thresholds
in the layout tests.
