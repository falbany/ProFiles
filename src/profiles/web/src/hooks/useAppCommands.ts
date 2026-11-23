/**
 * The application's command catalog (issue #224) — every action the user can
 * trigger, described once and consumed three ways:
 *
 * - `useGlobalShortcuts` dispatches key presses to the command bound to them;
 * - `ShortcutsModal` lists the commands that have a key binding;
 * - `CommandPalette` lists the palette-visible ones and runs them.
 *
 * The catalog is rebuilt on every render: each `run` closes over the deps of
 * that render. The key dispatcher deliberately captures the list it sees when
 * its effect subscribes (see `useGlobalShortcuts`), which keeps the
 * staleness profile the original inline handler had.
 *
 * `enabled` is part of the description, not a guard bolted on later: a
 * command that cannot run right now is still listed (the palette dims it and
 * shows `disabledReason`) and is skipped by the key dispatcher exactly as the
 * original handler's early `return`s did.
 */

import type { Dispatch, SetStateAction } from "react";

import type { ScannedFileItem } from "../api/types";
import type { ContextMenuPosition } from "../components/ContextMenu";
import { rowAnchorPoint } from "../utils/commands";
import type { Command } from "../utils/commands";
import { fileExtension, parentDirectory } from "../utils/fileProperties";

export interface AppCommandsDeps {
  /** The selection snapshot the "Selected file" commands act on. */
  visibleFiles: ScannedFileItem[];
  selectedIndex: number;
  /** View state that enables or disables commands. */
  activeDirectory: string;
  filterText: string;
  recursive: boolean;
  /** False while a scan runs or nothing is loaded. */
  canExport: boolean;

  moveSelection: (compute: (currentIndex: number, visibleCount: number) => number) => void;
  onContextMenu: (position: ContextMenuPosition) => void;
  onScan: () => void;
  onExecute: () => void;
  onProperties: (file: ScannedFileItem) => void;
  onReloadConfig: () => void;
  onGoHome: () => void;
  onToggleTheme: () => void;
  onBrowseDirectory: () => void;
  onGoToParentDirectory: () => void;
  onOpenActiveDirectory: () => void;
  onOpenDirectoryInTerminal: () => void;
  onClearFilter: () => void;
  onDisableRecursive: () => void;
  onLoadConfig: () => void;
  onExport: () => void;

  onReveal: (file: ScannedFileItem) => void;
  onOpenFolder: (file: ScannedFileItem) => void;
  onOpenTerminal: (file: ScannedFileItem) => void;
  onScanDirectory: (directory: string) => void;
  onFilterFolder: (folder: string) => void;
  onFilterExtension: (ext: string) => void;
  onCopyPath: (file: ScannedFileItem, forwardSlash?: boolean) => void;
  onCopyFilename: (file: ScannedFileItem, withoutExt?: boolean) => void;
  onCopyDirectory: (file: ScannedFileItem) => void;
  onCopyUri: (file: ScannedFileItem) => void;
  onComputeHash: (file: ScannedFileItem, algorithm: "md5" | "sha256") => void;
  onVerifyHash: (file: ScannedFileItem, algorithm: "md5" | "sha256") => void;
  onClearFile: (file: ScannedFileItem) => void;
  onGenerateBarcode: (file: ScannedFileItem) => void;
  /** Ask for command-line arguments, then launch through the normal path. */
  onRequestLaunchWithArgs: (file: ScannedFileItem) => void;

  setShowLogViewer: Dispatch<SetStateAction<boolean>>;
  setShowShortcuts: Dispatch<SetStateAction<boolean>>;
  setShowTimerModal: Dispatch<SetStateAction<boolean>>;
  setShowConfigEditor: Dispatch<SetStateAction<boolean>>;
  setShowLanModal: Dispatch<SetStateAction<boolean>>;
  setShowCameraScanner: Dispatch<SetStateAction<boolean>>;
  setShowCommandPalette: Dispatch<SetStateAction<boolean>>;
  setBarcodeMode: Dispatch<SetStateAction<boolean>>;
}

const NO_SELECTION = "Select a file first";

// Rows jumped by PageUp/PageDown in the file list (~a viewport of 28px rows).
const TABLE_PAGE_JUMP = 20;

/** Focus the first element matching *selector*. */
function focusField(selector: string): () => void {
  return () => document.querySelector<HTMLElement>(selector)?.focus();
}

export function useAppCommands(deps: AppCommandsDeps): Command[] {
  const { visibleFiles, selectedIndex } = deps;
  const file: ScannedFileItem | undefined = visibleFiles[selectedIndex];
  const hasSelection = Boolean(file);
  const hasDirectory = Boolean(deps.activeDirectory);
  const relFolder = parentDirectory(file?.rel_path ?? "");
  const extension = fileExtension(file?.filename ?? "");

  /** A command acting on the selected file; inert (and explained) without one. */
  const onSelection = (
    id: string,
    title: string,
    run: (file: ScannedFileItem) => void,
    keywords?: string[],
  ): Command => ({
    id,
    title,
    group: "selection",
    keywords,
    enabled: hasSelection,
    ...(hasSelection ? {} : { disabledReason: NO_SELECTION }),
    run: () => {
      if (file) run(file);
    },
  });

  return [
    // ── File list ─────────────────────────────────────────────────────────
    {
      id: "scan.run",
      title: "Rescan the file list",
      group: "file-list",
      keywords: ["refresh", "search"],
      keys: [{ key: "F5" }],
      // Enter inside a text field is the scan trigger of the original
      // handler; kept on the command so the rule stays visible here.
      fromInputEnter: true,
      // Always enabled on purpose: without a directory the scan is a silent
      // no-op, but F5 must still be claimed so the page does not reload.
      enabled: true,
      run: deps.onScan,
    },
    {
      id: "filter.clear",
      title: "Clear the filter",
      group: "file-list",
      keywords: ["search", "reset"],
      enabled: Boolean(deps.filterText.trim()),
      ...(deps.filterText.trim() ? {} : { disabledReason: "No filter is active" }),
      run: deps.onClearFilter,
    },
    {
      id: "scan.disableRecursive",
      title: "Turn off recursive scanning",
      group: "file-list",
      keywords: ["subdirectories"],
      enabled: deps.recursive,
      ...(deps.recursive ? {} : { disabledReason: "Recursive scanning is already off" }),
      run: deps.onDisableRecursive,
    },
    {
      // Always enabled on purpose: Enter is claimed even with nothing
      // selected (the launch itself is a no-op then), as before.
      id: "file.launch",
      title: "Launch the selected file",
      group: "file-list",
      keywords: ["open", "execute", "run"],
      keys: [{ key: "Enter" }],
      enabled: true,
      run: deps.onExecute,
    },
    {
      id: "file.properties",
      title: "Open file properties",
      group: "file-list",
      keys: [{ key: "p", ctrl: false, shift: false, alt: false }],
      enabled: hasSelection,
      ...(hasSelection ? {} : { disabledReason: NO_SELECTION }),
      run: () => {
        if (file) deps.onProperties(file);
      },
    },
    {
      id: "file.contextMenu",
      title: "Open the context menu for the selected file",
      group: "file-list",
      keywords: ["right click", "actions"],
      keys: [{ key: "ContextMenu" }, { key: "F10", shift: true }],
      enabled: hasSelection,
      ...(hasSelection ? {} : { disabledReason: NO_SELECTION }),
      run: () => {
        if (file) deps.onContextMenu({ ...rowAnchorPoint(selectedIndex), file });
      },
    },

    // ── Selected file ─────────────────────────────────────────────────────
    onSelection("file.launchWithArgs", "Launch with arguments…", deps.onRequestLaunchWithArgs, [
      "command line",
      "options",
    ]),
    onSelection("file.reveal", "Reveal in file manager", deps.onReveal, [
      "finder",
      "explorer",
      "show",
    ]),
    onSelection("file.openFolder", "Open the containing folder", deps.onOpenFolder, [
      "directory",
      "explorer",
    ]),
    onSelection(
      "file.openTerminal",
      "Open a terminal in the containing folder",
      deps.onOpenTerminal,
      ["shell", "cmd", "command line"],
    ),
    onSelection("file.scanDirectory", "Scan the containing directory", (selected) =>
      deps.onScanDirectory(parentDirectory(selected.path)),
    ),
    {
      id: "file.filterFolder",
      title: "Filter to the containing folder",
      group: "selection",
      keywords: ["subdirectory"],
      enabled: hasSelection && relFolder !== "",
      ...(!hasSelection
        ? { disabledReason: NO_SELECTION }
        : relFolder
          ? {}
          : { disabledReason: "The file is at the root of the scan" }),
      run: () => {
        if (file && relFolder) deps.onFilterFolder(relFolder);
      },
    },
    {
      id: "file.filterExtension",
      title: "Filter by this file's extension",
      group: "selection",
      keywords: ["type", "suffix"],
      enabled: hasSelection && extension !== "",
      ...(!hasSelection
        ? { disabledReason: NO_SELECTION }
        : extension
          ? {}
          : { disabledReason: "The file has no extension" }),
      run: () => {
        if (file && extension) deps.onFilterExtension(extension);
      },
    },
    onSelection("file.copyPath", "Copy full path", (selected) => deps.onCopyPath(selected, false), [
      "clipboard",
      "location",
    ]),
    onSelection(
      "file.copyPathForwardSlashes",
      "Copy path with forward slashes",
      (selected) => deps.onCopyPath(selected, true),
      ["clipboard", "unix"],
    ),
    onSelection(
      "file.copyFilename",
      "Copy file name",
      (selected) => deps.onCopyFilename(selected, false),
      ["clipboard"],
    ),
    onSelection(
      "file.copyFilenameWithoutExtension",
      "Copy file name without extension",
      (selected) => deps.onCopyFilename(selected, true),
      ["clipboard", "stem"],
    ),
    onSelection(
      "file.copyDirectory",
      "Copy the containing folder path",
      deps.onCopyDirectory,
      ["clipboard"],
    ),
    onSelection("file.copyUri", "Copy file URI", deps.onCopyUri, ["clipboard", "url", "link"]),
    onSelection(
      "file.hashMd5",
      "Compute MD5 hash",
      (selected) => deps.onComputeHash(selected, "md5"),
      ["checksum"],
    ),
    onSelection(
      "file.hashSha256",
      "Compute SHA-256 hash",
      (selected) => deps.onComputeHash(selected, "sha256"),
      ["sha256", "checksum"],
    ),
    onSelection(
      "file.verifyMd5",
      "Verify MD5 hash",
      (selected) => deps.onVerifyHash(selected, "md5"),
      ["checksum", "compare"],
    ),
    onSelection(
      "file.verifySha256",
      "Verify SHA-256 hash",
      (selected) => deps.onVerifyHash(selected, "sha256"),
      ["sha256", "checksum", "compare"],
    ),
    onSelection("file.qrCode", "Generate a QR code", deps.onGenerateBarcode, ["barcode", "share"]),
    onSelection("file.delete", "Delete file", deps.onClearFile, ["remove", "erase", "trash"]),

    // ── List navigation (key bindings only — nothing to pick in a palette) ──
    {
      id: "list.next",
      title: "Move to the next file",
      group: "file-list",
      palette: false,
      keys: [{ key: "ArrowDown" }],
      enabled: true,
      run: () => deps.moveSelection((prev, count) => Math.min(prev + 1, Math.max(0, count - 1))),
    },
    {
      id: "list.previous",
      title: "Move to the previous file",
      group: "file-list",
      palette: false,
      keys: [{ key: "ArrowUp" }],
      enabled: true,
      run: () => deps.moveSelection((prev) => Math.max(prev - 1, 0)),
    },
    {
      id: "list.first",
      title: "Jump to the first file",
      group: "file-list",
      palette: false,
      keys: [{ key: "Home" }],
      enabled: true,
      run: () => deps.moveSelection((prev) => (prev === 0 ? prev : 0)),
    },
    {
      id: "list.last",
      title: "Jump to the last file",
      group: "file-list",
      palette: false,
      keys: [{ key: "End" }],
      enabled: true,
      run: () =>
        deps.moveSelection((prev, count) => {
          const next = Math.max(0, count - 1);
          return prev === next ? prev : next;
        }),
    },
    {
      id: "list.pageUp",
      title: "Page up in the file list",
      group: "file-list",
      palette: false,
      keys: [{ key: "PageUp" }],
      enabled: true,
      run: () => deps.moveSelection((prev) => Math.max(prev - TABLE_PAGE_JUMP, 0)),
    },
    {
      id: "list.pageDown",
      title: "Page down in the file list",
      group: "file-list",
      palette: false,
      keys: [{ key: "PageDown" }],
      enabled: true,
      run: () =>
        deps.moveSelection((prev, count) =>
          Math.min(prev + TABLE_PAGE_JUMP, Math.max(0, count - 1)),
        ),
    },

    // ── Directory ─────────────────────────────────────────────────────────
    {
      id: "directory.home",
      title: "Go to the home directory",
      group: "navigation",
      keys: [{ key: "h", ctrl: true }],
      enabled: true,
      run: deps.onGoHome,
    },
    {
      id: "directory.parent",
      title: "Go to the parent directory",
      group: "navigation",
      enabled: hasDirectory,
      ...(hasDirectory ? {} : { disabledReason: "No directory is active" }),
      run: deps.onGoToParentDirectory,
    },
    {
      id: "directory.picker",
      title: "Browse for a directory",
      group: "navigation",
      keywords: ["folder", "choose"],
      enabled: true,
      run: deps.onBrowseDirectory,
    },
    {
      id: "directory.open",
      title: "Open the active directory in the file manager",
      group: "navigation",
      enabled: hasDirectory,
      ...(hasDirectory ? {} : { disabledReason: "No directory is active" }),
      run: deps.onOpenActiveDirectory,
    },
    {
      id: "directory.terminal",
      title: "Open the active directory in a terminal",
      group: "navigation",
      keywords: ["shell", "cmd"],
      enabled: hasDirectory,
      ...(hasDirectory ? {} : { disabledReason: "No directory is active" }),
      run: deps.onOpenDirectoryInTerminal,
    },

    // ── View ──────────────────────────────────────────────────────────────
    {
      id: "view.logViewer",
      title: "Open the log viewer",
      group: "view",
      keywords: ["logs"],
      keys: [{ key: "l", ctrl: true, shift: true }],
      enabled: true,
      run: () => deps.setShowLogViewer((prev) => !prev),
    },
    {
      id: "view.theme",
      title: "Switch theme (dark / light)",
      group: "view",
      keywords: ["toggle"],
      keys: [{ key: "t", ctrl: true, shift: true }],
      enabled: true,
      run: deps.onToggleTheme,
    },
    {
      id: "view.shortcuts",
      title: "Show keyboard shortcuts",
      group: "view",
      keys: [{ key: "?" }, { key: "/", ctrl: true }],
      enabled: true,
      run: () => deps.setShowShortcuts((prev) => !prev),
    },
    {
      id: "view.commandPalette",
      title: "Open the command palette",
      group: "view",
      keys: [{ key: "p", ctrl: true, shift: true }],
      enabled: true,
      run: () => deps.setShowCommandPalette(true),
    },

    // ── Configuration ─────────────────────────────────────────────────────
    {
      id: "config.reload",
      title: "Reload the configuration",
      group: "configuration",
      keys: [{ key: "r", ctrl: true }],
      enabled: true,
      run: deps.onReloadConfig,
    },
    {
      id: "config.editor",
      title: "Open the configuration editor",
      group: "configuration",
      keywords: ["yaml", "settings"],
      keys: [{ key: ",", ctrl: true }],
      enabled: true,
      run: () => deps.setShowConfigEditor(true),
    },
    {
      id: "config.load",
      title: "Load a configuration file…",
      group: "configuration",
      keywords: ["switch", "profiles"],
      enabled: true,
      run: deps.onLoadConfig,
    },

    // ── Tools ─────────────────────────────────────────────────────────────
    {
      id: "tools.barcodeMode",
      title: "Toggle barcode scanner mode",
      group: "tools",
      keys: [{ key: "b", ctrl: true, shift: false }],
      enabled: true,
      run: () => deps.setBarcodeMode((prev) => !prev),
    },
    {
      id: "tools.cameraScanner",
      title: "Open the camera barcode scanner",
      group: "tools",
      keywords: ["webcam", "qr"],
      keys: [{ key: "b", ctrl: true, shift: true }],
      enabled: true,
      run: () => deps.setShowCameraScanner((prev) => !prev),
    },
    {
      id: "tools.autoRescan",
      title: "Set the auto-rescan timer",
      group: "tools",
      keywords: ["interval", "refresh"],
      keys: [{ key: "t", ctrl: true, shift: false }],
      enabled: true,
      run: () => deps.setShowTimerModal(true),
    },
    {
      id: "tools.lan",
      title: "Open the LAN access modal",
      group: "tools",
      keywords: ["network", "bind"],
      keys: [{ key: "k", ctrl: true, shift: false }],
      enabled: true,
      run: () => deps.setShowLanModal(true),
    },
    {
      id: "tools.exportCsv",
      title: "Export the results as CSV",
      group: "tools",
      keywords: ["save", "spreadsheet"],
      enabled: deps.canExport,
      ...(deps.canExport ? {} : { disabledReason: "Nothing to export" }),
      run: deps.onExport,
    },

    // ── Focus ─────────────────────────────────────────────────────────────
    {
      id: "focus.directory",
      title: "Focus the directory field",
      group: "focus",
      keys: [{ key: "d", ctrl: true }],
      enabled: true,
      run: focusField("#directory-combobox"),
    },
    {
      id: "focus.extension",
      title: "Focus the extension field",
      group: "focus",
      keys: [{ key: "e", ctrl: true }],
      enabled: true,
      run: focusField("#extension-combobox"),
    },
    {
      id: "focus.filter",
      title: "Focus the filter field",
      group: "focus",
      keys: [{ key: "f", ctrl: true }],
      enabled: true,
      run: focusField("#filter-combobox"),
    },
    {
      // The only focus shortcut that also works while the caret sits in an
      // input or on a control — the original handler ran it before the
      // target guards, unlike Ctrl+D / Ctrl+E / Ctrl+F.
      id: "focus.fileList",
      title: "Focus the file list",
      group: "focus",
      keys: [{ key: "l", ctrl: true, shift: false }],
      beforeTargetGuard: true,
      enabled: true,
      run: focusField("[data-testid='file-list']"),
    },
  ];
}
