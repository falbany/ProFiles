import { describe, expect, it } from "vitest";

import type { ScannedFileItem } from "../api/types";
import { followSelection } from "./selection";

/** Minimal row fixture — only `path` matters to followSelection. */
function row(path: string): ScannedFileItem {
  return {
    filename: path.split("/").pop() || path,
    path,
    column_values: {},
    rel_path: path,
  };
}

describe("followSelection", () => {
  it("test_follow_selection_finds_moved_row", () => {
    // The previously selected row is still in the fresh set, but its index
    // moved to 5 — the selection must follow the path, not the stale index.
    const files = [
      row("C:/data/a.txt"),
      row("C:/data/b.txt"),
      row("C:/data/c.txt"),
      row("C:/data/d.txt"),
      row("C:/data/e.txt"),
      row("C:/data/moved.txt"),
    ];
    expect(followSelection("C:/data/moved.txt", files)).toBe(5);
  });

  it("test_follow_selection_absent_returns_minus_one", () => {
    // The row vanished from the fresh set — the caller hands the query to
    // restoreSelection (server lookup), never re-selects a neighbour.
    const files = [row("C:/data/a.txt"), row("C:/data/b.txt")];
    expect(followSelection("C:/data/gone.txt", files)).toBe(-1);
  });

  it("test_follow_selection_null_returns_minus_one", () => {
    // No previous path (never selected) → -1; the caller keeps its own
    // clamp for the untracked case.
    const files = [row("C:/data/a.txt")];
    expect(followSelection(null, files)).toBe(-1);
  });
});
