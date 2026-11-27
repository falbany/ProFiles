/** Directory preference merge shared by the two directory-selection paths.

Keeps `current` when it is among `candidates`, else the first candidate,
else `fallback`. The fallback encodes the two call sites' distinct
behaviors: directory picked keeps the current value when the new config
offers nothing matching, while directory changed resets to `""`.
 */
export function mergeDirectoryPreference(
  current: string,
  candidates: string[] | undefined,
  fallback: string,
): string {
  if (candidates?.includes(current)) return current;
  return candidates?.[0] ?? fallback;
}

/** Smallest number of depth options the UI always offers.

Ruled semantics: depth 1 = selected directory only, N = N levels below the
root. Even when the configured depth is smaller (or 0), the dropdown keeps
1..25 selectable, so the cap is dynamic: max(configured depth, 25).
 */
export const MIN_UI_SCAN_CAP = 25;

/** Depth value meaning "unlimited" scanning (int32 max).

Deliberately a plain number constant — UI state, the scan request and the
core all carry depth as a number/int, never an enum or a union type.
 */
export const UNLIMITED_SCAN_DEPTH = 2147483647;

/** List the depth options for the scan-depth dropdown: 1..cap.

Ruled semantics: depth 1 = selected directory only, N = N levels below the
root. The configured depth is never clamped above — the option list extends
to max(floor(configDepth) || MIN_UI_SCAN_CAP, MIN_UI_SCAN_CAP), so a config
of 0 or a fractional value falls back to the 25-entry default list.

Args:
  configDepth: configured max search depth, pre-clamped by the caller.
 */
export function buildDepthOptions(configDepth: number): number[] {
  const cap = Math.max(Math.floor(configDepth) || MIN_UI_SCAN_CAP, MIN_UI_SCAN_CAP);
  return Array.from({ length: cap }, (_, index) => index + 1);
}

/** Clamp a depth value, flooring at 1 only.

Ruled semantics: depth 1 = selected directory only, N = N levels below the
root. The value is never clamped above — large depths (including
UNLIMITED_SCAN_DEPTH) pass through unchanged.

Args:
  n: raw depth value to clamp.
 */
export function clampDepth(n: number): number {
  return Math.max(1, n);
}

/** Translate the legacy barcode `recursive` flag into a scan depth.

Ruled semantics: `false` scanned the selected directory only (depth 1),
`true` used the configured depth, and an absent flag leaves the current
value untouched. Callers pass `configDepth` pre-`clampDepth`; this helper
does not clamp.

Args:
  val: legacy recursive flag, or undefined when the config omits it.
  current: depth currently selected in the UI.
  configDepth: configured max search depth, pre-clamped by the caller.
 */
export function barcodeRecursiveToDepth(
  val: boolean | undefined,
  current: number,
  configDepth: number,
): number {
  if (val === undefined) return current;
  return val ? configDepth : 1;
}
