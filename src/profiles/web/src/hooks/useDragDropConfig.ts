import { useEffect, useRef, useState } from "react";
import { loadConfigContent } from "../api/client";
import type { AppConfigData } from "../api/types";
import {
  nextDragState,
  pickConfigFile,
  resetDragState,
  type DragTrackerState,
} from "../utils/configDrop";

/**
 * Window-level drag/drop of configuration files (issue #148 PR 6), moved
 * verbatim from `App.tsx`: the `dropOverlayVisible` state, the depth-counting
 * drag tracker (`dragStateRef` + `applyDragState`), `handleDroppedConfig`,
 * and the four window listeners (dragenter/dragover/dragleave/drop).
 *
 * Mechanism ruling (PR 3 precedent, see `useBarcodeMode`): the listeners
 * effect keeps its exact `[]` dep list and captures `const d = deps` INSIDE
 * the effect body — once per subscription, never through a per-render ref —
 * so its synchronous reads (`d.showToast` in onDrop's not-a-config branch)
 * keep the exact staleness windows the original inline effect had. The async
 * config apply is deliberately NOT part of that capture: `dropHandlerRef`
 * `.current` is reassigned at RENDER SCOPE (not inside an effect) to a
 * closure over this render's `handleDroppedConfig`, so every drop reads
 * `deps.onConfigLoaded`/`deps.showToast` from the CURRENT render — the
 * codebase's latest-ref idiom for an async consumer.
 *
 * Preserved quirks — do NOT "fix" (behavior-preserving extraction):
 * - onDrop's "Not a ProFiles configuration file." toast reads the
 *   FIRST-render `d.showToast` (identity churns per render — useToast is a
 *   plain closure — but its internals only touch stable setState, so the
 *   capture works);
 * - `handleDroppedConfig`'s catch swallows the error (no rethrow, no state
 *   change — the overlay was already reset synchronously by the drop
 *   itself, before the apply chain resolved).
 *
 * Escape seam: App's `onEscape` calls `resetDrop()` — a hard reset that
 * hides the overlay AND zeroes the tracker depth, because cancelled drags
 * may never fire dragleave (WKWebView).
 *
 * Pick seam (additive): `applyConfigFile` serves DropConfigOverlay's
 * click-to-pick path (App `onFileSelected`); window drops keep their
 * latest-ref routing through the render-scope reassignment.
 */
export function useDragDropConfig(deps: {
  onConfigLoaded: (cfg: AppConfigData) => Promise<void>;
  showToast: (msg: string, kind?: "info" | "error") => void;
}): {
  dropOverlayVisible: boolean;
  resetDrop: () => void;
  applyConfigFile: (file: File) => void;
} {
  // Dropped configuration files: window-level drag/drop, session-only trial.
  const [dropOverlayVisible, setDropOverlayVisible] = useState(false);
  const dragStateRef = useRef<DragTrackerState>(resetDragState());
  const applyDragState = (state: DragTrackerState) => {
    dragStateRef.current = state;
    setDropOverlayVisible(state.overlayVisible);
  };
  const dropHandlerRef = useRef<(file: File) => void>(() => {});

  const handleDroppedConfig = async (file: File) => {
    try {
      const content = await file.text();
      const cfg = await loadConfigContent(file.name, content);
      await deps.onConfigLoaded(cfg);
      deps.showToast(`Session config applied: ${file.name}`);
    } catch (err: any) {
      deps.showToast(err.message || "Failed to apply dropped configuration", "error");
    }
  };
  dropHandlerRef.current = (file: File) => {
    void handleDroppedConfig(file);
  };

  useEffect(() => {
    const d = deps;
    const hasFiles = (e: DragEvent) =>
      Array.from(e.dataTransfer?.types ?? []).includes("Files");
    const onDragEnter = (e: DragEvent) => {
      applyDragState(nextDragState(dragStateRef.current, "enter", hasFiles(e)));
    };
    const onDragOver = (e: DragEvent) => {
      if (hasFiles(e)) e.preventDefault();
    };
    const onDragLeave = (e: DragEvent) => {
      applyDragState(nextDragState(dragStateRef.current, "leave", hasFiles(e)));
    };
    const onDrop = (e: DragEvent) => {
      e.preventDefault();
      applyDragState(resetDragState());
      const files = Array.from(e.dataTransfer?.files ?? []);
      const picked = pickConfigFile(files);
      if (!picked) {
        if (files.length > 0) d.showToast("Not a ProFiles configuration file.", "error");
        return;
      }
      dropHandlerRef.current(picked);
    };
    window.addEventListener("dragenter", onDragEnter);
    window.addEventListener("dragover", onDragOver);
    window.addEventListener("dragleave", onDragLeave);
    window.addEventListener("drop", onDrop);
    return () => {
      window.removeEventListener("dragenter", onDragEnter);
      window.removeEventListener("dragover", onDragOver);
      window.removeEventListener("dragleave", onDragLeave);
      window.removeEventListener("drop", onDrop);
    };
  }, []);

  // Cancelled drags may never fire dragleave (WKWebView) — make
  // Escape a hard reset for the drop overlay.
  const resetDrop = () => {
    applyDragState(resetDragState());
  };

  // Additive seam for DropConfigOverlay's click-to-pick path (App's
  // onFileSelected): the same body the render-scope dropHandlerRef
  // reassignment holds — window drops keep their latest-ref routing.
  const applyConfigFile = (file: File) => {
    void handleDroppedConfig(file);
  };

  return { dropOverlayVisible, resetDrop, applyConfigFile };
}
