/** Filename rules for dropped configuration files (session-only trials).

Mirrors the server's accepted suffixes for ``POST /api/config/load-content``:
any ``*.profiles`` name (including the literal ``.profiles`` dotfile) plus
generic ``.yaml`` / ``.yml`` files.
 */

const ACCEPTED_SUFFIXES = [
  ".profiles",
  ".profiles.yaml",
  ".profiles.yml",
  ".yaml",
  ".yml",
] as const;

/** Return true when *name* is a configuration file the drop-zone accepts. */
export function isAcceptedConfigName(name: string): boolean {
  const lowered = name.toLowerCase();
  return ACCEPTED_SUFFIXES.some((suffix) => lowered.endsWith(suffix));
}

/** Return the first accepted File among *files*, or null when none match. */
export function pickConfigFile(files: File[]): File | null {
  for (const file of files) {
    if (isAcceptedConfigName(file.name)) {
      return file;
    }
  }
  return null;
}
