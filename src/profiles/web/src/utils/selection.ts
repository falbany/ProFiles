import type { ScannedFileItem } from "../api/types";

/**
 * Index of *previousPath* in *files*, or -1 when absent/null. Pure.
 *
 * The selection reconcile follows the previously selected row by path
 * across refreshes (#218): a fresh result set may reorder rows, but the
 * row's identity (path) persists, so the highlight moves with the file
 * instead of staying on the stale index. `-1` means "not visible here" —
 * the caller either restores it from the server (App's restoreSelection)
 * or keeps its own clamp for the never-selected case.
 */
export function followSelection(
  previousPath: string | null,
  files: ScannedFileItem[],
): number {
  if (!previousPath) return -1;
  return files.findIndex((f) => f.path === previousPath);
}
