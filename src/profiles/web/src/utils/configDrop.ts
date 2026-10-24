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

export interface DragTrackerState {
  depth: number;
  overlayVisible: boolean;
}

export type DragEventType = "enter" | "leave" | "drop";

export function resetDragState(): DragTrackerState {
  return { depth: 0, overlayVisible: false };
}

/** Pure reducer for the window-level drag lifecycle (overlay visibility).

The browser fires nested dragenter/dragleave pairs while crossing child
elements, so the depth counts all pairs; the overlay hides only when the
depth returns to zero (last leave) or the drop completes.
 */
export function nextDragState(
  state: DragTrackerState,
  eventType: DragEventType,
  hasFiles: boolean,
): DragTrackerState {
  switch (eventType) {
    case "enter": {
      if (!hasFiles) return state;
      const depth = state.depth + 1;
      return { depth, overlayVisible: true };
    }
    case "leave": {
      const depth = Math.max(0, state.depth - 1);
      return { depth, overlayVisible: state.depth > 0 && depth > 0 };
    }
    case "drop":
      return resetDragState();
  }
}
