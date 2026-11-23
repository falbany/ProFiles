import { useCallback, useEffect, useState } from "react";

/**
 * Recently used palette commands (issue #224) — the ids the command palette
 * lists first, newest first, remembered across sessions in
 * `localStorage["profiles-recent-commands"]`.
 *
 * The read is validated and guarded: anything but a JSON array of strings
 * (missing key, corrupt value, storage unavailable) reads as "no recents".
 * Writes are best-effort — a full or blocked storage must never break the
 * palette.
 */

const STORAGE_KEY = "profiles-recent-commands";

/** How many recents are kept — the size of the palette's "Recent" group. */
export const MAX_RECENT_COMMANDS = 8;

/** Parse the stored list; anything unexpected yields an empty list. */
export function parseRecentCommands(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return value.filter((id): id is string => typeof id === "string").slice(0, MAX_RECENT_COMMANDS);
  } catch {
    return [];
  }
}

/** *id* promoted to the front, duplicates removed, capped at *max*. */
export function pushRecentCommand(
  ids: readonly string[],
  id: string,
  max: number = MAX_RECENT_COMMANDS,
): string[] {
  return [id, ...ids.filter((existing) => existing !== id)].slice(0, max);
}

export function useRecentCommands(): {
  /** Command ids, newest first. */
  recentIds: string[];
  /** Record a command as just used. */
  touch: (id: string) => void;
} {
  // Both the storage access and the read itself can throw (blocked cookies,
  // sandboxed frame); either way the session starts without recents.
  const [recentIds, setRecentIds] = useState<string[]>(() => {
    try {
      return parseRecentCommands(window.localStorage.getItem(STORAGE_KEY));
    } catch {
      return [];
    }
  });

  // Persist on change (also re-writes the initial value, which is harmless
  // and repairs a corrupt entry on the first run).
  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(recentIds));
    } catch {
      // Best-effort: the recents simply won't survive a restart.
    }
  }, [recentIds]);

  const touch = useCallback((id: string) => {
    setRecentIds((previous) => pushRecentCommand(previous, id));
  }, []);

  return { recentIds, touch };
}
