import { useEffect } from "react";

import type { ScannedFileItem } from "../api/types";
import { findCommand } from "../utils/commands";
import type { Command } from "../utils/commands";

export interface GlobalShortcutsDeps {
  // Re-subscription cadence — the ORIGINAL effect's exact dep list. Only
  // `anyModalOpen` is read by the handler itself; the other seven exist
  // because they decide WHEN the captured command list is refreshed (see
  // the ruling below).
  anyModalOpen: boolean;
  visibleFiles: ScannedFileItem[];
  selectedIndex: number;
  activeDirectory: string;
  activeExtension: string;
  filterText: string;
  recursive: boolean;
  barcodeMode: boolean;
  /** The command catalog (`useAppCommands`) this handler dispatches to. */
  commands: Command[];
  /** Escape — the one key that reaches the app even while a modal is open. */
  onEscape: () => void;
}

/**
 * Global keyboard dispatcher (issue #148 PR 3, reshaped onto the command
 * registry by issue #224).
 *
 * The handler owns the order of the guards, and nothing else:
 *
 * 1. Escape always reaches `onEscape`, modal open or not.
 * 2. While a modal / context menu is open every other key is inert (#55).
 * 3. Commands flagged `beforeTargetGuard` run wherever the caret is.
 * 4. Keys landing on a control that handles them itself are left alone
 *    (#55); inside a text input or select only Enter is acted on, by the
 *    command flagged `fromInputEnter`; textarea and contenteditable hosts
 *    (the config editor's CodeMirror) are fully inert — typing owns those
 *    keys, including Enter (#247).
 * 5. Otherwise the first enabled command bound to the key runs.
 *
 * Which key does what lives in the registry (`useAppCommands`).
 *
 * IMPORTANT (review ruling): `const d = deps;` is captured INSIDE the effect
 * body — once per subscription, never through a per-render ref. The
 * commands therefore keep the exact staleness windows the original inline
 * effect had (e.g. a second Ctrl+R re-entering during an in-flight reload
 * keeps invoking the first closure until a dep-changing state update
 * re-subscribes). `useGlobalShortcuts.test.tsx` pins this in both
 * directions; do not "fix" it with refs or memoization. The effect does NOT
 * depend on `deps.commands`: the list is rebuilt every render, and taking
 * its identity as a dependency would re-subscribe each time and silently
 * erase that profile.
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

      // The focus helper that must also work from inside an input or on a
      // control runs before the target guards can stop it.
      const early = findCommand(d.commands, e, (command) => command.beforeTargetGuard === true);
      if (early) {
        e.preventDefault();
        early.run();
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

      // Multi-line / rich typing surfaces (textarea, and contenteditable
      // hosts such as the config editor's CodeMirror) belong to the caret:
      // no global command runs from there, and Enter is NOT the scan rule —
      // it must keep inserting a newline (issue #247).
      if (
        target instanceof HTMLTextAreaElement ||
        (target instanceof HTMLElement && target.isContentEditable)
      ) {
        return;
      }

      // If typing in input / select, handle Enter for scan
      if (target instanceof HTMLInputElement || target instanceof HTMLSelectElement) {
        if (e.key === "Enter") {
          // Deliberately not preventDefault-ed — the original rule left the
          // key to the combobox as well.
          d.commands.find((command) => command.fromInputEnter && command.enabled)?.run();
        }
        return;
      }

      // Everything else: the first enabled command bound to the key.
      const command = findCommand(d.commands, e, (candidate) => !candidate.beforeTargetGuard);
      if (command) {
        e.preventDefault();
        command.run();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [deps.anyModalOpen, deps.visibleFiles, deps.selectedIndex, deps.activeDirectory, deps.activeExtension, deps.filterText, deps.recursive, deps.barcodeMode]);
}
