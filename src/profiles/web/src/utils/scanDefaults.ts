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
