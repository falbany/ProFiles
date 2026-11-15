/**
 * Version display helpers (issue #175).
 *
 * hatch-vcs produces long PEP 440 local versions in development builds, e.g.
 * `0.12.0b1.dev35+gc05201dfa.d20261115`. The header only shows the release
 * part; the complete string stays available (tooltip).
 */

/**
 * Extract the short, user-facing part of a version string.
 *
 * Strips the `.devN` segment and the local (`+...`) segment of a PEP 440
 * version, keeping the release. Anything that does not look like a version
 * is passed through unchanged.
 *
 * @param version Full version string, e.g. `0.12.0b1.dev35+gc05201dfa.d20261115`
 * @returns Short version, e.g. `0.12.0b1`
 */
export function shortVersion(version: string): string {
  if (!version) return "";
  // Cut at the first `.devN` / `.postN` segment, or at the local segment.
  const match = version.match(/^(.*?)\.(?:dev|post)\d+/);
  if (match) return match[1];
  const plus = version.indexOf("+");
  if (plus > -1) return version.slice(0, plus);
  return version;
}
