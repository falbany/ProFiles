import { useEffect } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { ContextMenuPosition } from "../components/ContextMenu";
import type { ScannedFileItem } from "../api/types";

// Rows jumped by PageUp/PageDown in the file list (~a viewport of 28px rows).
const TABLE_PAGE_JUMP = 20;

export interface GlobalShortcutsDeps {
  // Re-subscription cadence — the ORIGINAL effect's exact dep list.
  anyModalOpen: boolean;
  visibleFiles: ScannedFileItem[];
  selectedIndex: number;
  activeDirectory: string;
  activeExtension: string;
  filterText: string;
  recursive: boolean;
  barcodeMode: boolean;
  // Handlers captured at subscription time (same staleness windows as today).
  onEscape: () => void;
  onContextMenu: (pos: ContextMenuPosition) => void;
  onExecute: () => void;
  onScan: () => void;
  onReloadConfig: () => void;
  onGoHome: () => void;
  onProperties: (file: ScannedFileItem) => void;
  onToggleTheme: () => void;
  // React setters, passed raw (stable identities; functional updates preserved).
  setShowLogViewer: Dispatch<SetStateAction<boolean>>;
  setShowShortcuts: Dispatch<SetStateAction<boolean>>;
  setShowTimerModal: Dispatch<SetStateAction<boolean>>;
  setShowConfigEditor: Dispatch<SetStateAction<boolean>>;
  setShowLanModal: Dispatch<SetStateAction<boolean>>;
  setBarcodeMode: Dispatch<SetStateAction<boolean>>;
  setShowCameraScanner: Dispatch<SetStateAction<boolean>>;
  // Selection — functional-updater style; App writes selectedPathRef inside the updater.
  moveSelection: (compute: (currentIndex: number, visibleCount: number) => number) => void;
}

/**
 * Global keyboard navigation & shortcuts (issue #148 PR 3), moved verbatim
 * from `App.tsx`'s window keydown effect.
 *
 * IMPORTANT (review ruling): `const d = deps;` is captured INSIDE the effect
 * body — once per subscription, never through a per-render ref. The handlers
 * therefore keep the exact staleness windows the original inline effect had
 * (e.g. a second Ctrl+R re-entering during an in-flight reload keeps
 * invoking the first closure until a dep-changing state update
 * re-subscribes). `useGlobalShortcuts.test.tsx` pins this in both
 * directions; do not "fix" it with refs or memoization.
 *
 * Re-subscription follows the ORIGINAL effect's dep list — the state fields
 * below — so fresh per-render callback identities alone never tear the
 * listener down.
 */
export function useGlobalShortcuts(deps: GlobalShortcutsDeps): void {
  useEffect(() => {
    const d = deps;
    const handleKeyDown = (e: KeyboardEvent) => {
      // Allow Esc to close context menu or modals
      if (e.key === "Escape") {
        d.onEscape();
        return;
      }

      // Shortcuts are inert while a modal / context menu is open (issue #55).
      if (d.anyModalOpen) return;

      if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        document.querySelector<HTMLElement>("[data-testid='file-list']")?.focus();
        return;
      }

      // Keys landing on a control that handles them itself (activation,
      // sort, resize…) must not also drive the file list (issue #55).
      const target = e.target;
      if (
        target instanceof HTMLElement &&
        target.closest("button, a, [role='menuitem'], [role='option'], [role='columnheader'], [role='separator']")
      ) {
        return;
      }

      // If typing in input / select, handle Enter for scan
      if (target instanceof HTMLInputElement || target instanceof HTMLSelectElement) {
        if (e.key === "Enter") {
          d.onScan();
        }
        return;
      }

      if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
        const file = d.visibleFiles[d.selectedIndex];
        if (!file) return;
        e.preventDefault();
        const row = document.querySelector<HTMLElement>(`[data-row-index="${d.selectedIndex}"]`);
        const rect = row?.getBoundingClientRect();
        d.onContextMenu({
          x: rect ? rect.left + 24 : 24,
          y: rect ? rect.top + rect.height / 2 : 24,
          file,
        });
        return;
      }

      // F5: Refresh
      if (e.key === "F5") {
        e.preventDefault();
        d.onScan();
        return;
      }

      // Ctrl + R: Reload config & scan
      if (e.ctrlKey && e.key.toLowerCase() === "r") {
        e.preventDefault();
        d.onReloadConfig();
        return;
      }

      // Ctrl + D: Focus directory
      if (e.ctrlKey && e.key.toLowerCase() === "d") {
        e.preventDefault();
        document.querySelector<HTMLInputElement>("#directory-combobox")?.focus();
        return;
      }

      // Ctrl + E: Focus extension
      if (e.ctrlKey && e.key.toLowerCase() === "e") {
        e.preventDefault();
        document.querySelector<HTMLInputElement>("#extension-combobox")?.focus();
        return;
      }

      // Ctrl + F: Focus filter
      if (e.ctrlKey && e.key.toLowerCase() === "f") {
        e.preventDefault();
        document.querySelector<HTMLInputElement>("#filter-combobox")?.focus();
        return;
      }

      // Ctrl + Shift + L: Open the log viewer
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        d.setShowLogViewer((prev) => !prev);
        return;
      }

      // Ctrl + ,: Open the in-app config editor (issue #95) — same entry
      // point as the status-bar Config button; the OS-launch this shortcut
      // used to perform lives in the editor header ("Open in OS").
      if (e.ctrlKey && e.key === ",") {
        e.preventDefault();
        d.setShowConfigEditor(true);
        return;
      }

      // Ctrl + K: Open the LAN access modal (issues #197/#198/#199) — same
      // entry point as the status-bar LAN button. Ctrl+N was the requested
      // mnemonic, but browsers reserve it for "new window" and a page can
      // never intercept it, so the LAN modal lands on Ctrl + K.
      if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        d.setShowLanModal(true);
        return;
      }

      // Ctrl + Shift + T: Cycle theme
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "t") {
        e.preventDefault();
        d.onToggleTheme();
        return;
      }

      // Ctrl + B: Toggle barcode scanner mode
      if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "b") {
        e.preventDefault();
        d.setBarcodeMode((prev) => !prev);
        return;
      }

      // Ctrl + Shift + B: Open camera barcode scanner
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "b") {
        e.preventDefault();
        d.setShowCameraScanner((prev) => !prev);
        return;
      }

      // Ctrl + T: Open timer modal
      if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "t") {
        e.preventDefault();
        d.setShowTimerModal(true);
        return;
      }

      // Ctrl + H: Go to home directory
      if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "h") {
        e.preventDefault();
        void d.onGoHome();
        return;
      }

      // ? or Ctrl + /: Show shortcuts
      if (e.key === "?" || (e.ctrlKey && e.key === "/")) {
        e.preventDefault();
        d.setShowShortcuts((prev) => !prev);
        return;
      }

      // P: Open file properties (when a file is selected)
      if (e.key.toLowerCase() === "p" && !e.ctrlKey && !e.shiftKey && !e.altKey) {
        const file = d.visibleFiles[d.selectedIndex];
        if (file) {
          e.preventDefault();
          d.onProperties(file);
        }
        return;
      }

      // Table navigation — indexed over the VISIBLE (filtered) rows.
      if (e.key === "ArrowDown") {
        e.preventDefault();
        d.moveSelection((prev, count) => Math.min(prev + 1, Math.max(0, count - 1)));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        d.moveSelection((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Home") {
        e.preventDefault();
        d.moveSelection((prev) => (prev === 0 ? prev : 0));
      } else if (e.key === "End") {
        e.preventDefault();
        d.moveSelection((prev, count) => {
          const next = Math.max(0, count - 1);
          return prev === next ? prev : next;
        });
      } else if (e.key === "PageUp") {
        e.preventDefault();
        d.moveSelection((prev) => Math.max(prev - TABLE_PAGE_JUMP, 0));
      } else if (e.key === "PageDown") {
        e.preventDefault();
        d.moveSelection(
          (prev, count) => Math.min(prev + TABLE_PAGE_JUMP, Math.max(0, count - 1)),
        );
      } else if (e.key === "Enter") {
        e.preventDefault();
        d.onExecute();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [deps.anyModalOpen, deps.visibleFiles, deps.selectedIndex, deps.activeDirectory, deps.activeExtension, deps.filterText, deps.recursive, deps.barcodeMode]);
}
