import { useEffect, useMemo, useRef, useState } from "react";
import {
  computeHash,
  fetchConfig,
  fetchScanResults,
  fetchSystemInfo,
  findScanResultsPath,
  launchFile,
  openFolder,
  openLogFile,
  openTerminal,
  revealFile,
  selectDirectory,
  browseDirectory,
  reloadConfig,
  exportCsvToDisk,
} from "./api/client";
import type { AppConfigData, ScannedFileItem, SystemInfo } from "./api/types";
import { resolveSessionTheme } from "./utils/theme";
import { barcodeRecursiveToDepth, clampDepth, mergeDirectoryPreference } from "./utils/scanDefaults";
import { useScanController } from "./hooks/useScanController";
import { useScanProgress } from "./hooks/useScanProgress";
import { useToast } from "./hooks/useToast";
import { useExternalEvents } from "./hooks/useExternalEvents";
import { useGlobalShortcuts } from "./hooks/useGlobalShortcuts";
import { appendFilterTerm, useAppCommands } from "./hooks/useAppCommands";
import { useRecentCommands } from "./hooks/useRecentCommands";
import { useAutoRescanTimer } from "./hooks/useAutoRescanTimer";
import { useWatchMode } from "./hooks/useWatchMode";
import { useBarcodeMode } from "./hooks/useBarcodeMode";
import { useTheme } from "./hooks/useTheme";
import { useDragDropConfig } from "./hooks/useDragDropConfig";
import { ActionBar } from "./components/ActionBar";
import { CommandPalette } from "./components/CommandPalette";
import { ConfigEditorModal } from "./components/ConfigEditorModal";
import { ContextMenu, type ContextMenuPosition } from "./components/ContextMenu";
import { DirectoryPickerModal } from "./components/DirectoryPickerModal";
import { DropConfigOverlay } from "./components/DropConfigOverlay";
import { FileListTable } from "./components/FileListTable";
import { HeaderBar } from "./components/HeaderBar";
import { InitErrorPanel } from "./components/InitErrorPanel";
import { LanModal } from "./components/LanModal";
import { SearchBar } from "./components/SearchBar";
import { LogViewerModal } from "./components/LogViewerModal";
import { LoadConfigModal } from "./components/LoadConfigModal";
import type { ConfigPickerMode } from "./components/LoadConfigModal";
import { FilePropertiesModal } from "./components/FilePropertiesModal";
import { LaunchArgsDialog } from "./components/LaunchArgsDialog";
import { BarcodeModal } from "./components/BarcodeModal";
import { CameraBarcodeModal } from "./components/CameraBarcodeModal";
import { SingleMatchPromptModal } from "./components/SingleMatchPromptModal";
import { StatusBar } from "./components/StatusBar";
import { TimerModal } from "./components/TimerModal";
import { WorkflowRunnerModal } from "./components/WorkflowRunnerModal";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { exportToCsv } from "./utils/exportCsv";
import { pathToFileUri } from "./utils/fileUri";
import { followSelection } from "./utils/selection";
import { matchFilter } from "./utils/searchSyntax";
import { parentDirectory } from "./utils/fileProperties";

/** Debounce for the client-side prefilter derivation while typing (lane #1). */
const PREFILTER_DEBOUNCE_MS = 120;

export default function App() {
  const { theme, applyTheme, toggleTheme } = useTheme();
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [config, setConfig] = useState<AppConfigData | null>(null);
  const [activeDirectory, setActiveDirectory] = useState<string>("");
  const [activeExtension, setActiveExtension] = useState<string>("");
  const [filterText, setFilterText] = useState<string>("");
  /**
   * Scan depth (#240): 1 = selected directory only, N = up to N levels,
   * ∞ = unlimited (`UNLIMITED_SCAN_DEPTH`). Session-only — nothing here
   * writes depth back to any file. `configDepth` mirrors the configured
   * depth (clamped) that sizes the SearchBar option list.
   */
  const [depth, setDepth] = useState<number>(10);
  const [configDepth, setConfigDepth] = useState<number>(10);

  /** Reason the initial load failed, when it did — drives the retry panel. */
  const [initError, setInitError] = useState<string | null>(null);
  const [initRetrying, setInitRetrying] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  // Bluetooth-free prefilter — the perceptibly-instant client-side list.
  // The query applied to the list lags the input by ~120ms so a burst of
  // keystrokes only re-derives the filter once (see lane #1).
  const [prefilterQuery, setPrefilterQuery] = useState("");

  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const { toastMessage, showToast, dismissToast } = useToast();
  const [reloading, setReloading] = useState<boolean>(false);
  const [language, setLanguage] = useState<"en" | "fr">("en");
  const [showDirPicker, setShowDirPicker] = useState<boolean>(false);
  /**
   * Config picker intent (issue #192): null = closed, "create" = the
   * first-run auto-prompt, "load" = an explicit Load/Choose action. The
   * mode lives HERE because the caller knows why the picker opened;
   * LoadConfigModal no longer infers it from the global config state.
   */
  const [configPickerMode, setConfigPickerMode] = useState<ConfigPickerMode | null>(null);
  // In-app YAML configuration editor (issue #95), opened from the StatusBar
  // "Config" button. The old OS-launch behavior moved into the editor's
  // header ("Open in OS").
  const [showConfigEditor, setShowConfigEditor] = useState<boolean>(false);
  /**
   * Bumped when the config picker loads a different .profiles file (issue
   * #101): an editor left open underneath re-runs its load-on-open fetch
   * so it swaps to the freshly picked content. Apply/Save do NOT bump it —
   * they already drive the editor through onApplied.
   */
  const [editorReloadKey, setEditorReloadKey] = useState<number>(0);
  const [showPropertiesModal, setShowPropertiesModal] = useState<boolean>(false);
  // File awaiting delete confirmation (in-app dialog — window.confirm is a
  // no-op inside the desktop webviews, issue #31).
  const [pendingDeleteFile, setPendingDeleteFile] = useState<ScannedFileItem | null>(null);
  const [propertiesFile, setPropertiesFile] = useState<ScannedFileItem | null>(null);
  const [showLogViewer, setShowLogViewer] = useState<boolean>(false);
  const [showTimerModal, setShowTimerModal] = useState<boolean>(false);
  /** LAN access modal visibility — one modal for enable and disable. */
  const [lanModalOpen, setLanModalOpen] = useState(false);

  /** Command palette visibility (issue #224). */
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  /** File awaiting command-line arguments ("Launch with arguments…"). */
  const [argsFile, setArgsFile] = useState<ScannedFileItem | null>(null);
  /** Recently used palette commands, newest first. */
  const { recentIds, touch: touchRecentCommand } = useRecentCommands();

  // Workflow Modal state
  const [workflowLaunchParams, setWorkflowLaunchParams] = useState<{
    file: ScannedFileItem;
    args?: string;
  } | null>(null);

  // QR code modal — shows a generated QR for sharing a file location.
  const [showBarcodeModal, setShowBarcodeModal] = useState<boolean>(false);
  const [barcodeFilePath, setBarcodeFilePath] = useState<string | undefined>(undefined);

  // Verify-hash manual entry — clipboard reads are refused on some webviews,
  // so the expected hash is typed in instead (issue #141).
  const [verifyHashPrompt, setVerifyHashPrompt] = useState<{
    file: ScannedFileItem;
    algorithm: "md5" | "sha256";
  } | null>(null);
  const [verifyHashInput, setVerifyHashInput] = useState<string>("");

  // Camera Barcode Scanner & Single match prompt state
  const [showCameraScanner, setShowCameraScanner] = useState<boolean>(false);
  const [singleMatchFile, setSingleMatchFile] = useState<ScannedFileItem | null>(null);

  /** Open the LAN modal; it reflects the live bind state and offers the
   *  opposite action, so the requested direction from the header is unused. */
  const toggleLan = (_next: boolean) => {
    setLanModalOpen(true);
  };

  /**
   * Path of the currently selected row. Selection is re-anchored by path when
   * the visible (filtered) set changes, so it never silently drifts onto an
   * unrelated file.
   */
  const selectedPathRef = useRef<string | null>(null);

  /**
   * Selection-restore dedupe (#218): the reconcile effect re-fires on every
   * visible-set change, so while a server lookup for a vanished row is in
   * flight, identical re-entries for the same path must not stack.
   */
  const restoreInFlightRef = useRef<string | null>(null);

  /**
   * Current search-bar state as scan parameters — the single source shared
   * by the scan controller and the barcode hook (issue #148 PR 4).
   */
  const getScanParams = () => ({ directory: activeDirectory, extension: activeExtension, filter_text: filterText, max_depth: depth });

  /**
   * Scan orchestration (issue #148): list state, the generation protocol,
   * the deferred server auto-rescan, sort reloads and paging live in the
   * hook. App keeps the UI-side concerns — toasts (showToast) and selection
   * (the reconcile effect re-anchors it; see onFreshResults below).
   */
  const scan = useScanController({
    showToast,
    getScanParams,
    // Selection follows the previous path on every fresh result set (#218)
    // — the reconcile effect owns it; nothing to reset here. (The old
    // `selectedPathRef.current = null; setSelectedIndex(0)` reset WAS the
    // #218 bug: it dropped the path the reconcile effect needs to follow.)
    onFreshResults: () => {},
  });

  /**
   * True while the startup (initial-load) scan is in flight (#152): the
   * controller's `scanning` flag deliberately stays false during it (the
   * init panel owns that feedback), but the strip should still show live
   * progress for what is usually the session's longest scan. Drives the
   * strip gate together with `scan.scanning` and opens the SSE stream.
   */
  const [initialScanActive, setInitialScanActive] = useState(false);
  const scanProgress = useScanProgress(scan.scanning || initialScanActive);

  /**
   * Barcode scanner mode (issue #148 PR 4): the mode state + buffer, the
   * wedge capture listener, the toggle and the camera handler live in the
   * hook; App supplies the value appliers and keeps the single-match and
   * camera-modal surfaces.
   */
  const {
    barcodeMode, setBarcodeMode, handleBarcodeToggle, handleCameraDetected,
  } = useBarcodeMode({
    showToast,
    scanWith: scan.scanWith,
    getScanParams,
    configDepth,
    onApplyValues: (values) => {
      if (values.filter !== undefined) setFilterText(values.filter);
      if (values.ext !== undefined) setActiveExtension(values.ext);
      if (values.recursive !== undefined) setDepth(barcodeRecursiveToDepth(values.recursive, depth, configDepth));
      if (values.dir !== undefined) setActiveDirectory(values.dir);
    },
    onSingleMatch: setSingleMatchFile,
    onCameraClose: () => setShowCameraScanner(false),
    setFilterText,
  });

  // Derive the prefilter query from the raw input, debounced ~120ms so a
  // keystroke burst only re-filters the loaded list once.
  useEffect(() => {
    if (!filterText.trim()) {
      // Empty query short-circuits: the visible list IS the loaded list.
      setPrefilterQuery("");
      return;
    }
    const id = window.setTimeout(() => setPrefilterQuery(filterText), PREFILTER_DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [filterText]);

  /** Rows rendered in the table — prefiltered client-side over rel_path. */
  const visibleFiles = useMemo(
    () =>
      prefilterQuery.trim() === ""
        ? scan.files
        : scan.files.filter((f) => matchFilter(f.rel_path, prefilterQuery, f.attrs)),
    [scan.files, prefilterQuery],
  );

  /**
   * Coverage hint (lane #1): the loaded page is smaller than the backend's
   * full result set, so the prefilter only describes part of it — point the
   * user at the full server search (Enter).
   */
  const prefilterNote =
    filterText.trim() && scan.files.length < scan.totalCount
      ? `Prefiltering loaded results — press Enter to search all ${scan.totalCount}`
      : null;

  // Selection reconcile (#218): when a new visible set arrives, follow the
  // previously selected file (matched by path) if it is still visible — even
  // though its index moved. Rows never selected keep the clamp into the
  // visible set; a selected row that vanished is asked of the server
  // (restoreSelection) and either comes back with its window or clears.
  useEffect(() => {
    const queryPath = selectedPathRef.current;
    if (!queryPath) {
      // Never selected (or already cleared): clamp into the visible set.
      setSelectedIndex((prev) => Math.min(prev, Math.max(0, visibleFiles.length - 1)));
      return;
    }
    const followed = followSelection(queryPath, visibleFiles);
    if (followed >= 0) {
      setSelectedIndex((prev) => (followed !== prev ? followed : prev));
      return;
    }
    // Not in the visible set: the server knows whether the row moved beyond
    // the loaded window or is gone (#218).
    void restoreSelection(queryPath);
  }, [visibleFiles]);

  const handleReloadConfig = async () => {
    if (reloading) return;
    setReloading(true);
    showToast("Reloading configuration...");

    const scanGeneration = scan.beginScan();

    try {
      // 1. Fetch fresh system info (in case hostname/IP changed)
      const sys = await fetchSystemInfo();
      setSystemInfo(sys);

      // 2. Ask the server to re-parse the attached config file from disk
      //    (GET /api/config only returns the in-memory snapshot).
      const cfg = await reloadConfig();
      setConfig(cfg);

      // Theme from the freshly loaded config, like handleConfigLoaded does
      // (a reload trial — #129: it must not persist over the stored pref).
      applyTheme(resolveSessionTheme(cfg.theme), { persist: false });

      // 3. Apply the FRESH values from the response — not the stale
      //    closure state captured before the reload. The server re-derives
      //    active_directory from the reloaded config (launch resolution),
      //    and the first merged extension/filter match what a launch
      //    with this config would apply.
      const targetDirectory = cfg.active_directory || activeDirectory;
      const nextExtension = cfg.extensions[0] ?? "";
      const nextFilter = cfg.filters[0] ?? "";
      if (targetDirectory) {
        setActiveDirectory(targetDirectory);
      }
      setActiveExtension(nextExtension);
      setFilterText(nextFilter);
      const d = clampDepth(cfg.max_search_depth);
      setConfigDepth(d);
      setDepth(d);

      if (cfg.reloaded === false) {
        showToast(
          `Config file not found: ${cfg.config_path || "(unknown path)"} — kept current configuration.`,
          "error",
        );
      } else {
        showToast("Configuration reloaded.");
      }

      // 4. Run fresh scan with the reloaded values
      if (targetDirectory) {
        await scan.scanWithGeneration(scanGeneration, {
          directory: targetDirectory,
          extension: nextExtension,
          filter_text: nextFilter,
          max_depth: d,
        }, { errorPrefix: "Failed to reload configuration" });
      }
    } catch (err: any) {
      showToast(`Failed to reload configuration: ${err.message}`, "error");
    } finally {
      setReloading(false);
      // Finish scan if it's still the current generation
      scan.finishScan(scanGeneration);
    }
  };

  const handleConfigLoaded = async (cfg: AppConfigData) => {
    const scanGeneration = scan.beginScan();
    setConfig(cfg);
    // Session-only configs apply their theme to the running session but
    // must NOT persist it (no localStorage write — that would leak the
    // trial into the next session).
    applyTheme(resolveSessionTheme(cfg.theme), { persist: false });
    // Loading a config must behave like launching with it: the server
    // re-derived active_directory from the NEW config (the stale directory
    // is never sent back), and the first merged extension/filter is what a
    // launch would apply — values kept from the previous configuration
    // would belong to the old directory's machine config.
    const targetDirectory = cfg.active_directory || activeDirectory || (cfg.directories[0] ?? "");
    const nextExtension = cfg.extensions[0] ?? "";
    const nextFilter = cfg.filters[0] ?? "";
    if (targetDirectory) {
      setActiveDirectory(targetDirectory);
    }
    setActiveExtension(nextExtension);
    setFilterText(nextFilter);
    const d = clampDepth(cfg.max_search_depth);
    setConfigDepth(d);
    setDepth(d);

    if (!cfg.session_trial) {
      showToast(cfg.config_exists ? `Loaded config: ${cfg.config_path}` : "Starter configuration created.");
    }
    if (targetDirectory) {
      await scan.scanWithGeneration(scanGeneration, {
        directory: targetDirectory,
        extension: nextExtension,
        filter_text: nextFilter,
        max_depth: d,
      }, { errorPrefix: "Scan failed after config load" });
    } else {
      scan.finishScan(scanGeneration);
    }
  };

  // Dropped configuration files: window-level drag/drop, session-only trial.
  const { dropOverlayVisible, resetDrop, applyConfigFile } = useDragDropConfig({
    onConfigLoaded: handleConfigLoaded,
    showToast,
  });

  // Config handoff notifications (issue #4) — the poll lives in the hook;
  // App injects the re-apply (fresh config + handleConfigLoaded) and the toast.
  useExternalEvents({
    onConfigApplied: async () => {
      const cfg = await fetchConfig();
      await handleConfigLoaded(cfg);
    },
    showToast,
  });

  const handleBrowseDirectory = () => {
    setShowDirPicker(true);
  };

  const handleDirectoryPicked = async (directory: string) => {
    const scanGeneration = scan.beginScan();
    setShowDirPicker(false);
    setActiveDirectory(directory);
    showToast(`Directory selected: ${directory}`);
    let directoryConfig: AppConfigData | undefined;
    try {
      directoryConfig = await selectDirectory(directory);
      setConfig(directoryConfig);
    } catch (err: any) {
      // Non-fatal: directory is already applied in the UI
      console.error("select-directory failed:", err);
    }
    if (!scan.isCurrentScan(scanGeneration)) return;
    const nextExtension = mergeDirectoryPreference(
      activeExtension,
      directoryConfig?.extensions,
      activeExtension,
    );
    const nextFilter = mergeDirectoryPreference(filterText, directoryConfig?.filters, filterText);
    setActiveExtension(nextExtension);
    setFilterText(nextFilter);
    // Scan with the freshly picked directory
    await scan.scanWithGeneration(scanGeneration, {
      directory,
      extension: nextExtension,
      filter_text: nextFilter,
      max_depth: depth,
    }, { errorPrefix: "Scan failed" });
  };

  const initializeFromConfig = async (cfg: AppConfigData, scanGeneration: number) => {
    if (!scan.isCurrentScan(scanGeneration)) return;
    
    // Apply the theme from the .profiles configuration with highest
    // priority, persisting it — the config is the source of truth at
    // startup, so only this path writes localStorage (#129: the reload and
    // trial paths below apply session-only themes without persisting).
    applyTheme(resolveSessionTheme(cfg.theme), { persist: true });
    
    setConfig(cfg);
    const initialDir = cfg.active_directory || (cfg.directories.length > 0 ? cfg.directories[0] : "");
    const initialExt = cfg.extensions.length > 0 ? cfg.extensions[0] : "";
    const initialFilter = cfg.filters.length > 0 ? cfg.filters[0] : "";
    if (initialDir) setActiveDirectory(initialDir);
    if (initialExt) setActiveExtension(initialExt);
    const d = clampDepth(cfg.max_search_depth);
    setConfigDepth(d);
    setDepth(d);
    if (initialFilter) setFilterText(initialFilter);
    if (!cfg.config_exists) {
      // First-run auto-prompt: the ONLY entry point that proposes create.
      setConfigPickerMode("create");
    }

    if (initialDir) {
      setInitialScanActive(true);
      try {
        await scan.runScan(scanGeneration, {
          directory: initialDir,
          extension: initialExt,
          filter_text: initialFilter,
          max_depth: d,
        });
      } catch (scanErr: any) {
        if (scan.isCurrentScan(scanGeneration)) showToast(`Initial scan failed: ${scanErr.message}`, "error");
      } finally {
        setInitialScanActive(false);
      }
    }
  };

  // Initial load (also re-run by the retry panel when it fails).
  const runInitialLoad = async () => {
    // A retry must abort any in-flight scan fetch from the failed load
    // (issue #34) — claimGeneration, no spinner: the init panel owns the
    // feedback and no auto-rescan is scheduled yet.
    const scanGeneration = scan.claimGeneration();
    setInitError(null);
    setInitRetrying(true);
    try {
      const sys = await fetchSystemInfo();
      setSystemInfo(sys);
      const cfg = await fetchConfig();
      await initializeFromConfig(cfg, scanGeneration);
    } catch (err: any) {
      // Initial load failure is recoverable — surface it in a retry panel
      // instead of a toast so the user has a place to act from.
      setInitError(err?.message || "Couldn't fetch system info or configuration.");
    } finally {
      setInitRetrying(false);
    }
  };

  useEffect(() => {
    void runInitialLoad();
  }, []);

  // Directory change handler. Resolves to true when the directory was
  // selected and scanned successfully, false otherwise — callers use this
  // to avoid a success toast after a handled failure (issue #130).
  const handleDirectoryChange = async (newDir: string): Promise<boolean> => {
    const scanGeneration = scan.beginScan();
    setActiveDirectory(newDir);
    try {
      const directoryConfig = await selectDirectory(newDir);
      if (!scan.isCurrentScan(scanGeneration)) return false;
      setConfig(directoryConfig);
      const nextExtension = mergeDirectoryPreference(activeExtension, directoryConfig.extensions, "");
      const nextFilter = mergeDirectoryPreference(filterText, directoryConfig.filters, "");
      setActiveExtension(nextExtension);
      setFilterText(nextFilter);
      return (await scan.scanWithGeneration(scanGeneration, {
        directory: newDir,
        extension: nextExtension,
        filter_text: nextFilter,
        max_depth: depth,
      }, { errorPrefix: "Directory change failed" })).ok;
    } catch (err: any) {
      if (scan.isCurrentScan(scanGeneration)) showToast(`Directory change failed: ${err.message}`, "error");
      return false;
    } finally {
      scan.finishScan(scanGeneration);
    }
  };

  // Run scan
  const handleScan = async () => {
    await scan.scanWith(
      { directory: activeDirectory, extension: activeExtension, filter_text: filterText, max_depth: depth },
      { errorPrefix: "Scan failed" },
    );
  };

  // Timer — periodic rescan (issue #34): the hook owns the interval state and
  // the tick effect; its latest-deps ref keeps this closure current, so every
  // tick scans with the CURRENT directory/extension/filter.
  const { autoRescanInterval, handleTimerSet } = useAutoRescanTimer({
    scan: () => {
      void handleScan();
    },
    showToast,
  });

  // Watch mode (#223): the SSE feed is the truth — the hook rescans on a
  // watch_seq bump (deferring exactly one trailing scan past a running
  // scan) and reconciles the toggle with the server payload.
  const watch = useWatchMode({
    scan: () => {
      void handleScan();
    },
    showToast,
    isScanning: () => scan.scanning,
  });

  // Two modes of one control (#223): the timer and the watch are mutually
  // exclusive. Enabling the watch turns a running timer off first; toggling
  // an active watch off is the plain disable.
  const handleWatchToggle = () => {
    if (watch.watching) {
      void watch.handleWatchSet(false);
    } else {
      if (autoRescanInterval > 0) handleTimerSet(0);
      void watch.handleWatchSet(true);
    }
  };

  /** Timer setter that first turns the watch off (#223) when arming a new
   *  interval — the timer path of the mutual exclusion above. */
  const handleTimerSetExclusive = (seconds: number) => {
    if (seconds > 0 && watch.watching) void watch.handleWatchSet(false);
    handleTimerSet(seconds);
  };

  /**
   * Filter input handler (SearchBar onChange). Applies the text instantly
   * for the client-side prefilter, then schedules the deferred server
   * auto-rescan 800ms after the last keystroke.
   */
  const handleFilterTextChange = (text: string) => {
    setFilterText(text);
    scan.scheduleDeferredRescan();
  };

  /**
   * Depth select handler (SearchBar, #240). Applies the picked depth to
   * state, then schedules the same deferred server auto-rescan as the
   * filter input — so picking a depth rescans immediately instead of
   * waiting for the next explicit scan.
   */
  const handleDepthChange = (next: number) => {
    setDepth(next);
    scan.scheduleDeferredRescan();
  };

  /**
   * Extension combobox handler (SearchBar). The server already scanned with
   * the previous extension, so a change must rescan — the same deferred
   * auto-rescan as the filter input and depth select (issue #122).
   */
  const handleExtensionChange = (ext: string) => {
    setActiveExtension(ext);
    scan.scheduleDeferredRescan();
  };

  const handleClearFilter = async () => {
    setFilterText("");
    await scan.scanWith(
      { directory: activeDirectory, extension: activeExtension, filter_text: "", max_depth: depth },
      { errorPrefix: "Scan failed" },
    );
  };

  /**
   * Filter-preset command (issue #227): append the operator term to the
   * current filter as an implicit AND via the pure `appendFilterTerm` and
   * the plain setter — the same state path as handleClearFilter. No server
   * rescan: the prefilter effect applies the composed text to the loaded
   * list, exactly as after a keystroke.
   */
  const handleAppendFilterTerm = (term: string) => {
    setFilterText(appendFilterTerm(filterText, term));
  };

  /** Re-run the scan at depth 1 — selected directory only (empty-state action;
   *  the FileListTable label keeps saying "Turn off recursive", #240). */
  const handleDisableRecursive = async () => {
    setDepth(1);
    await scan.scanWith(
      { directory: activeDirectory, extension: activeExtension, filter_text: filterText, max_depth: 1 },
      { errorPrefix: "Scan failed" },
    );
  };

  // Launch file
  const handleLaunch = async (file: ScannedFileItem, extraArgs?: string) => {
    if (file.has_hook) {
      setWorkflowLaunchParams({ file, args: extraArgs });
      return;
    }
    try {
      await launchFile({
        directory: activeDirectory,
        filename: file.rel_path,
        release: config?.release,
        args: extraArgs,
      });
      showToast(`Launched ${file.filename}`);
    } catch (err: any) {
      showToast(`Launch error: ${err.message}`, "error");
    }
  };

  // A cleared selection is `-1` — an inert "nothing selected" (#218): the
  // vanished row must never silently land on another file. No guard change
  // needed here — `visibleFiles[-1]` is undefined, so the existing check
  // simply launches nothing.
  const handleExecute = () => {
    if (visibleFiles.length > 0 && visibleFiles[selectedIndex]) {
      handleLaunch(visibleFiles[selectedIndex]);
    }
  };

  /** Row-click selection — re-anchors the selection tracker by path. */
  const handleSelectIndex = (idx: number) => {
    selectedPathRef.current = visibleFiles[idx]?.path ?? null;
    setSelectedIndex(idx);
  };

  /**
   * Recover the selection for a row that left the visible set (#218). Called
   * by the reconcile effect when followSelection missed. The row either
   * moved beyond the loaded window — fetch that window in ONE request and
   * append it, letting the reconcile effect re-select from the enlarged
   * visible set — or is genuinely gone / filtered away, and the selection
   * clears instead of drifting onto another file.
   *
   * Best-effort: a failed lookup leaves the selection untouched (the next
   * visible-set change retries through the reconcile effect); every state
   * write is dropped when another scan superseded this one mid-flight, or
   * when the user re-anchored the selection during the lookup round-trip
   * (ownership guard — a restore that no longer owns the selection must
   * neither clear it nor re-anchor it, #218 final review).
   */
  const restoreSelection = async (path: string) => {
    const gen = scan.currentGeneration();
    // All rows are already loaded: absence from the visible set is decidable
    // locally — the row is either filtered away or gone; both clear. No
    // server round-trip needed (and no await before the clear, so no user
    // click can interleave).
    if (scan.files.length >= scan.totalCount) {
      if (!scan.isCurrentScan(gen)) return;
      selectedPathRef.current = null;
      setSelectedIndex(-1);
      return;
    }
    // One in-flight restore per path — identical re-entries (the reconcile
    // effect re-fires on every visible-set change) are dropped.
    if (restoreInFlightRef.current === path) return;
    restoreInFlightRef.current = path;
    try {
      const { offset } = await findScanResultsPath({
        path,
        sort_by: scan.sort?.column,
        sort_dir: scan.sort?.direction,
      });
      if (!scan.isCurrentScan(gen)) return;
      // Ownership guard (final review, #218): the lookup round-trip is not
      // instant — if the user clicked another row while it was in flight,
      // this restore no longer owns the selection.
      if (selectedPathRef.current !== path) return;
      if (offset < 0 || offset < scan.files.length) {
        // Genuinely gone from the server set (`offset: -1`), or loaded but
        // hidden by the prefilter — the user filtered it away, and clearing
        // is honest (#218).
        selectedPathRef.current = null;
        setSelectedIndex(-1);
        return;
      }
      // The row lives beyond the loaded window: fetch the missing span in
      // ONE request, append it (dedupe-by-path in the controller), then let
      // the reconcile effect re-fire on the new visibleFiles and follow.
      const res = await fetchScanResults({
        offset: scan.files.length,
        limit: Math.min(offset + 1 - scan.files.length, 50_000),
        sort_by: scan.sort?.column,
        sort_dir: scan.sort?.direction,
      });
      if (!scan.isCurrentScan(gen)) return;
      if (selectedPathRef.current !== path) return;
      scan.appendResults(gen, res);
    } catch {
      // Non-fatal: keep the current selection until the next reconcile.
    } finally {
      restoreInFlightRef.current = null;
    }
  };

  // Context menu actions
  /** "Launch with arguments…" (context menu, command palette): ask first,
   *  then launch through the normal path so hooks still apply. */
  const requestLaunchWithArgs = (file: ScannedFileItem) => setArgsFile(file);

  /** Copy the folder containing *file* (context menu, command palette). */
  const handleCopyDirectory = async (file: ScannedFileItem) => {
    const dirPath = parentDirectory(file.path);
    try {
      // Await the write: clipboard failures (permissions, insecure context)
      // must not report success (issue #35).
      await navigator.clipboard.writeText(dirPath);
      showToast(`Copied: ${dirPath}`);
    } catch (err: unknown) {
      showToast(`Copy failed: ${err instanceof Error ? err.message : String(err)}`, "error");
    }
  };

  const handleReveal = async (file: ScannedFileItem) => {
    try {
      await revealFile(file.path);
      showToast("Revealed in file manager.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`, "error");
    }
  };

  const handleOpenFolder = async (file: ScannedFileItem) => {
    try {
      await openFolder(file.path);
      showToast("Folder opened in file manager.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`, "error");
    }
  };

  const handleOpenTerminal = async (file: ScannedFileItem) => {
    try {
      const res = await openTerminal(file.path);
      showToast(res.message || "Terminal opened.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`, "error");
    }
  };

  const handleScanDirectory = async (directory: string) => {
    // handleDirectoryChange already toasts its own failure and never throws;
    // only claim success when the change + scan went through (issue #130).
    const ok = await handleDirectoryChange(directory);
    if (ok) showToast(`Scanned directory: ${directory}`);
  };

  const handleFilterFolder = (folder: string) => {
    setFilterText(folder);
    void scan.scanWith(
      { directory: activeDirectory, extension: activeExtension, filter_text: folder, max_depth: depth },
      { errorPrefix: "Scan failed" },
    );
  };

  const handleFilterExtension = (ext: string) => {
    setActiveExtension(ext);
    void scan.scanWith(
      { directory: activeDirectory, extension: ext, filter_text: filterText, max_depth: depth },
      { errorPrefix: "Scan failed" },
    );
  };

  const handleCopyPath = async (file: ScannedFileItem, forwardSlash?: boolean) => {
    const p = forwardSlash ? file.path.replace(/\\/g, "/") : file.path;
    try {
      await navigator.clipboard.writeText(p);
      showToast("Path copied to clipboard.");
    } catch (err: any) {
      showToast(`Copy failed: ${err?.message ?? err}`, "error");
    }
  };

  const handleCopyFilename = async (file: ScannedFileItem, withoutExt?: boolean) => {
    let name = file.filename;
    if (withoutExt) {
      const idx = name.lastIndexOf(".");
      if (idx !== -1) name = name.slice(0, idx);
    }
    try {
      await navigator.clipboard.writeText(name);
      showToast("Filename copied to clipboard.");
    } catch (err: any) {
      showToast(`Copy failed: ${err?.message ?? err}`, "error");
    }
  };

  const handleComputeHash = async (file: ScannedFileItem, algorithm: "md5" | "sha256") => {
    try {
      showToast(`Computing ${algorithm.toUpperCase()}...`);
      const res = await computeHash(file.path, algorithm);
      await navigator.clipboard.writeText(res.hash);
      showToast(`${algorithm.toUpperCase()} hash copied: ${res.hash.slice(0, 12)}...`);
    } catch (err: any) {
      showToast(`Hash computation failed: ${err.message}`, "error");
    }
  };

  const handleCopyUri = async (file: ScannedFileItem) => {
    try {
      const uri = pathToFileUri(file.path);
      await navigator.clipboard.writeText(uri);
      showToast("File URI copied to clipboard.");
    } catch (err: any) {
      showToast(`URI copy failed: ${err.message}`, "error");
    }
  };

  const runHashVerification = async (
    file: ScannedFileItem,
    algorithm: "md5" | "sha256",
    expectedHash: string,
  ) => {
    showToast(`Computing ${algorithm.toUpperCase()}...`);
    try {
      const res = await computeHash(file.path, algorithm);
      const match = res.hash.toLowerCase() === expectedHash.trim().toLowerCase();
      if (match) {
        showToast(`✅  ${algorithm.toUpperCase()} matches!`);
      } else {
        showToast(`❌  ${algorithm.toUpperCase()} mismatch`);
      }
    } catch (err: any) {
      showToast(`Verification failed: ${err.message}`, "error");
    }
  };

  const handleVerifyHash = async (file: ScannedFileItem, algorithm: "md5" | "sha256") => {
    let clipboardText: string;
    try {
      clipboardText = await navigator.clipboard.readText();
    } catch {
      // Clipboard reads are commonly refused inside the desktop webviews
      // (WKWebView / WebKitGTK) — fall back to manual entry instead of dying
      // with an "empty clipboard"-style error (issue #141).
      setVerifyHashInput("");
      setVerifyHashPrompt({ file, algorithm });
      return;
    }
    if (!clipboardText.trim()) {
      showToast("Clipboard is empty — copy a hash first, then try again.");
      return;
    }
    await runHashVerification(file, algorithm, clipboardText);
  };

  const handleProperties = (file: ScannedFileItem) => {
    setPropertiesFile(file);
    setShowPropertiesModal(true);
  };

  // Opens the in-app delete confirmation (window.confirm is a no-op inside
  // the desktop webviews — issue #31).
  const handleClearFile = (file: ScannedFileItem) => {
    setPendingDeleteFile(file);
  };

  const confirmDeleteFile = async () => {
    const file = pendingDeleteFile;
    setPendingDeleteFile(null);
    if (!file) return;
    try {
      showToast("Deleting file...");
      const res = await fetch(`/api/actions/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: file.path }),
      });
      if (!res.ok) throw new Error("Failed to delete file");
      showToast("File deleted successfully.");
      // Refresh the file list
      handleScan();
    } catch (err: any) {
      showToast(`Delete failed: ${err.message}`, "error");
    }
  };


  const handleGenerateBarcode = (file: ScannedFileItem) => {
    setBarcodeFilePath(file.path);
    setShowBarcodeModal(true);
  };

  const handleOpenActiveDirectory = async () => {
    if (!activeDirectory) return;
    try {
      await openFolder(activeDirectory);
      showToast("Directory opened in file manager.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`, "error");
    }
  };

  const handleOpenDirectoryInTerminal = async (directory: string) => {
    if (!directory) return;
    try {
      await openTerminal(directory);
      showToast("Terminal opened in directory.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`, "error");
    }
  };

  const handleGoToHomeDirectory = async () => {
    try {
      // "~" resolves to the OS home directory on the backend via expanduser()
      await handleDirectoryChange("~");
      showToast("Directory set to home folder.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`, "error");
    }
  };

  const handleGoToParentDirectory = async () => {
    if (!activeDirectory) return;
    try {
      const result = await browseDirectory(activeDirectory);
      if (result.parent_path) {
        await handleDirectoryChange(result.parent_path);
        showToast("Moved to parent directory.");
      } else {
        showToast("Already at root directory.");
      }
    } catch (err: any) {
      showToast(`Error: ${err.message}`, "error");
    }
  };

  const handleExport = async () => {
    if (scan.files.length === 0) {
      showToast("No files to export.");
      return;
    }
    try {
      const csvContent = exportToCsv(scan.files, config?.column_names || [], config ?? undefined, filterText);
      const filename = `profiles-export-${new Date().toISOString().slice(0, 19).replace(/[:.]/g, "-")}.csv`;
      // Saved server-side: browser blob downloads navigate to raw CSV inside the desktop webview.
      const result = await exportCsvToDisk(csvContent, filename);
      // Be explicit about scope: this exports the LOADED rows only (issue
      // #35), not the whole backend result set.
      showToast(
        `Exported ${scan.files.length} loaded row${scan.files.length === 1 ? "" : "s"}` +
        `${filterText ? ` matching "${filterText}"` : ""} — ${result.message}`,
      );
    } catch (err: any) {
      showToast(`Export failed: ${err.message}`, "error");
    }
  };

  // Keyboard navigation & global shortcuts
  // Any open surface that captures interaction: while one is up the global
  // shortcuts must stay inert (issue #55) — otherwise Enter/keys double-fire
  // into the hidden UI behind the dialog.
  const anyModalOpen = Boolean(
    contextMenuPos ||
      showDirPicker ||
      configPickerMode !== null ||
      showPropertiesModal ||
      showLogViewer ||
      showTimerModal ||
      showBarcodeModal ||
      showCameraScanner ||
      singleMatchFile ||
      workflowLaunchParams ||
      Boolean(pendingDeleteFile) ||
      showCommandPalette ||
      Boolean(argsFile),
  );
  // Plain function (builder call): the file uses no useCallback precedent, and
  // the hook captures deps at subscription time, so moveSelection's per-render
  // identity is harmless — do NOT memoize.
  const moveSelection = (compute: (currentIndex: number, visibleCount: number) => number) => {
    setSelectedIndex((prev) => {
      const next = compute(prev, visibleFiles.length);
      selectedPathRef.current = visibleFiles[next]?.path ?? null;
      return next;
    });
  };
  /**
   * The command catalog (issue #224): every action the UI exposes, described
   * once for the key dispatcher, the shortcuts sheet and the palette. Built
   * here because each command closes over App's state and handlers.
   */
  const commands = useAppCommands({
    visibleFiles,
    selectedIndex,
    activeDirectory,
    filterText,
    recursive: depth > 1,
    canExport: scan.files.length > 0 && !scan.scanning,
    moveSelection,
    onContextMenu: setContextMenuPos,
    onScan: handleScan,
    onExecute: handleExecute,
    onProperties: handleProperties,
    onReloadConfig: handleReloadConfig,
    onGoHome: handleGoToHomeDirectory,
    onToggleTheme: () => toggleTheme({ persist: true }),
    onBrowseDirectory: handleBrowseDirectory,
    onGoToParentDirectory: handleGoToParentDirectory,
    onOpenActiveDirectory: handleOpenActiveDirectory,
    onOpenDirectoryInTerminal: () => handleOpenDirectoryInTerminal(activeDirectory),
    onClearFilter: handleClearFilter,
    onAppendFilterTerm: handleAppendFilterTerm,
    onDisableRecursive: handleDisableRecursive,
    onLoadConfig: () => setConfigPickerMode("load"),
    onExport: handleExport,
    onReveal: handleReveal,
    onOpenFolder: handleOpenFolder,
    onOpenTerminal: handleOpenTerminal,
    onScanDirectory: handleScanDirectory,
    onFilterFolder: handleFilterFolder,
    onFilterExtension: handleFilterExtension,
    onCopyPath: handleCopyPath,
    onCopyFilename: handleCopyFilename,
    onCopyDirectory: handleCopyDirectory,
    onCopyUri: handleCopyUri,
    onComputeHash: handleComputeHash,
    onVerifyHash: handleVerifyHash,
    onClearFile: handleClearFile,
    onGenerateBarcode: handleGenerateBarcode,
    onRequestLaunchWithArgs: requestLaunchWithArgs,
    setShowLogViewer,
    setShowTimerModal,
    setShowConfigEditor,
    setShowLanModal: setLanModalOpen,
    setShowCameraScanner,
    setShowCommandPalette,
    setBarcodeMode,
  });
  const onEscape = () => {
    setContextMenuPos(null);
    setShowLogViewer(false);
    setShowTimerModal(false);
    setShowCommandPalette(false);
    resetDrop(); // hard reset lives in useDragDropConfig (WKWebView dragleave gap)
  };
  useGlobalShortcuts({
    anyModalOpen,
    visibleFiles,
    selectedIndex,
    activeDirectory,
    activeExtension,
    filterText,
    recursive: depth > 1,
    barcodeMode,
    commands,
    onEscape,
  });

  return (
    <div className="flex h-dvh flex-col bg-elevated/30 p-1 font-sans text-ink transition-colors duration-200 sm:p-1.5">
      {/* Rounded app frame — thin modern border around the whole app. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-frame-line bg-app shadow-[0_2px_6px_rgb(0_0_0/0.35)] transition-colors duration-200 sm:rounded-xl">
      <HeaderBar
        title={config?.title || ""}
        release={config?.release || ""}
        directories={config?.directories || []}
        activeDirectory={activeDirectory}
        onDirectoryChange={handleDirectoryChange}
        onBrowseDirectory={handleBrowseDirectory}
        onGoToParentDirectory={handleGoToParentDirectory}
        onGoToHomeDirectory={handleGoToHomeDirectory}
        onOpenActiveDirectory={handleOpenActiveDirectory}
        onOpenTerminal={handleOpenDirectoryInTerminal}
      />

      <SearchBar
        extensions={config?.extensions || []}
        activeExtension={activeExtension}
        onExtensionChange={handleExtensionChange}
        filterOptions={config?.filters || []}
        filterText={filterText}
        onFilterTextChange={handleFilterTextChange}
        depth={depth}
        onDepthChange={handleDepthChange}
        configDepth={configDepth}
        onScan={handleScan}
        scanning={scan.scanning}
        barcodeMode={barcodeMode}
        onBarcodeToggle={handleBarcodeToggle}
        onCameraBarcodeClick={() => setShowCameraScanner(true)}
        autoRescanActive={autoRescanInterval > 0}
        onTimerClick={() => setShowTimerModal(true)}
        watchActive={watch.watching}
        watchDisabled={scan.scanning || !activeDirectory}
        watchLabel={watch.watchIntervalS ? `${Math.round(watch.watchIntervalS)}s` : null}
        onWatchToggle={handleWatchToggle}
      />

      {initError ? (
        <InitErrorPanel
          message={initError}
          onRetry={() => void runInitialLoad()}
          retrying={initRetrying}
        />
      ) : (
        <FileListTable
          files={visibleFiles}
          totalCount={scan.totalCount}
          rawLoadedCount={scan.files.length}
          onLoadMore={scan.handleLoadMore}
          loadingMore={scan.loadingMore}
          scanning={scan.scanning}
          hasScanned={scan.hasScanned}
          activeDirectory={activeDirectory}
          recursive={depth > 1}
          onDisableRecursive={handleDisableRecursive}
          onOpenDirectory={handleOpenActiveDirectory}
          // FileList empty-state "Choose configuration" (issue #192): an
          // explicit choose action always opens the picker in Load mode.
          onLoadConfig={() => setConfigPickerMode("load")}
          filterText={filterText}
          onClearFilter={handleClearFilter}
          columnHeaders={config?.column_headers || []}
          columnNames={config?.column_names || []}
          selectedIndex={selectedIndex}
          onSelectIndex={handleSelectIndex}
          prefilterNote={prefilterNote}
          onLaunch={handleLaunch}
          onContextMenu={(e, file, idx) => {
            e.preventDefault();
            selectedPathRef.current = file.path;
            setSelectedIndex(idx);
            setContextMenuPos({ x: e.clientX, y: e.clientY, file });
          }}
          rowColors={config?.row_colors || []}
          sort={scan.sort}
          onSortChange={scan.applySort}
        />
      )}

      <ActionBar
        onExecute={handleExecute}
        scanning={scan.scanning}
        scanningDirectory={activeDirectory}
        initialScanActive={initialScanActive}
        scanProgress={scanProgress}
        hasSelection={visibleFiles.length > 0}
        fileCount={visibleFiles.length}
        totalCount={scan.totalCount}
        toastMessage={toastMessage}
        onToastDismiss={dismissToast}
      />

      <StatusBar
        systemInfo={systemInfo}
        fileCount={scan.totalCount}
        theme={theme}
        onToggleTheme={() => toggleTheme({ persist: true })}
        onOpenLog={() => setShowLogViewer(true)}
        onOpenCommandPalette={() => setShowCommandPalette(true)}
        // Repurposed (issue #95): opens the in-app YAML editor. The OS-launch
        // this button used to perform now lives in the editor's header
        // ("Open in OS"); the modal's onApplied drives handleConfigLoaded,
        // the same refresh path as LoadConfigModal and the drag/drop trial.
        // Config LOADING no longer lives here (issue #101): the editor's
        // "Load config file…" raises the picker from inside the editor.
        onOpenConfig={() => setShowConfigEditor(true)}
        onReloadConfig={handleReloadConfig}
        onExport={handleExport}
        exportDisabled={scan.files.length === 0 || scan.scanning}
        language={language}
        onLanguageChange={setLanguage}
        lanEnabled={systemInfo?.lan_enabled ?? null}
        onToggleLan={toggleLan}
      />
      </div>

      {/* YAML Configuration Editor (issue #95): Apply/Save/Save As hand the
          fresh AppConfigData to the shared handleConfigLoaded refresh path.
          Rendered BEFORE the picker so the picker — raised from inside the
          editor via onLoadConfig (issue #101) — paints on top (same z-scale
          token; DOM order decides). */}
      <ConfigEditorModal
        open={showConfigEditor}
        onClose={() => setShowConfigEditor(false)}
        onApplied={handleConfigLoaded}
        // Editor header "Load config file…" (issue #192): an explicit load
        // action opens the picker in Load mode, never the first-run Create.
        onLoadConfig={() => setConfigPickerMode("load")}
        reloadKey={editorReloadKey}
      />

      {/* Config Picker Modal. onLoaded ALSO bumps the editor's reload key
          so an editor left open underneath re-fetches the freshly picked
          file instead of keeping stale text (issue #101). */}
      <LoadConfigModal
        isOpen={configPickerMode !== null}
        mode={configPickerMode ?? "load"}
        activeConfigPath={config?.config_path}
        onClose={() => setConfigPickerMode(null)}
        onLoaded={(cfg) => {
          void handleConfigLoaded(cfg);
          setEditorReloadKey((key) => key + 1);
        }}
      />

      {/* Dropped configuration files (session-only trial) */}
      <DropConfigOverlay
        visible={dropOverlayVisible}
        onFileSelected={applyConfigFile}
      />

      {/* Directory Picker Modal */}
      <DirectoryPickerModal
        isOpen={showDirPicker}
        initialPath={activeDirectory}
        onClose={() => setShowDirPicker(false)}
        onSelect={handleDirectoryPicked}
      />

      {/* Context Menu */}
      <ContextMenu
        position={contextMenuPos}
        onClose={() => setContextMenuPos(null)}
        onLaunch={handleLaunch}
        onRequestLaunchWithArgs={requestLaunchWithArgs}
        onReveal={handleReveal}
        onOpenFolder={handleOpenFolder}
        onOpenTerminal={handleOpenTerminal}
        onScanDirectory={handleScanDirectory}
        onFilterFolder={handleFilterFolder}
        onFilterExtension={handleFilterExtension}
        onCopyPath={handleCopyPath}
        onCopyFilename={handleCopyFilename}
        onCopyDirectory={handleCopyDirectory}
        onCopyUri={handleCopyUri}
        onComputeHash={handleComputeHash}
        onVerifyHash={handleVerifyHash}
        onProperties={handleProperties}
        onClearFile={handleClearFile}
        onGenerateBarcode={handleGenerateBarcode}
      />

      {/* File Properties Modal */}
      <FilePropertiesModal
        isOpen={showPropertiesModal}
        file={propertiesFile}
        onLaunch={handleLaunch}
        onClose={() => {
          setShowPropertiesModal(false);
          setPropertiesFile(null);
        }}
      />

      {/* Timer Modal */}
      <TimerModal
        isOpen={showTimerModal}
        currentInterval={autoRescanInterval}
        onClose={() => setShowTimerModal(false)}
        onSetInterval={handleTimerSetExclusive}
      />

      {/* Log Viewer Modal */}
      <LogViewerModal
        isOpen={showLogViewer}
        onClose={() => setShowLogViewer(false)}
        onOpenExternally={() => {
          openLogFile()
            .then((r) => showToast(r.message))
            .catch((err: unknown) =>
              showToast(
                err instanceof Error ? err.message : "Failed to open the log file",
                "error",
              ),
            );
        }}
      />

      {/* Workflow Runner Modal */}
      <WorkflowRunnerModal
        isOpen={Boolean(workflowLaunchParams)}
        onClose={() => setWorkflowLaunchParams(null)}
        directory={activeDirectory}
        filename={workflowLaunchParams?.file.rel_path || ""}
        release={config?.release}
        args={workflowLaunchParams?.args}
        onFinished={(status, msg) => {
          if (status === "completed") {
            showToast(msg || "Workflow launched successfully.");
          } else if (status === "aborted" || status === "failed") {
            showToast(`Workflow stopped: ${msg}`, "error");
          }
        }}
      />

      {/* QR Code Modal */}
      <BarcodeModal
        isOpen={showBarcodeModal}
        onClose={() => {
          setShowBarcodeModal(false);
          setBarcodeFilePath(undefined);
        }}
        initialFilePath={barcodeFilePath}
      />

      {/* Verify-hash manual entry (issue #141) — the clipboard-based path is
          unavailable inside webviews that refuse clipboard reads. */}
      {verifyHashPrompt && (
        <div
          className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
          onClick={() => setVerifyHashPrompt(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="verify-hash-title"
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.preventDefault();
                event.stopPropagation();
                setVerifyHashPrompt(null);
              }
            }}
            onClick={(event) => event.stopPropagation()}
            className="animate-modal-in w-[440px] max-w-full rounded-2xl border border-frame-line glass-panel p-5"
          >
            <h2 id="verify-hash-title" className="mb-1 text-sm font-semibold text-ink">
              Verify {verifyHashPrompt.algorithm.toUpperCase()}
            </h2>
            <p className="mb-3 text-xs text-ink-muted">
              Clipboard access is unavailable here — paste the expected hash below.
            </p>
            <input
              autoFocus
              type="text"
              value={verifyHashInput}
              onChange={(event) => setVerifyHashInput(event.target.value)}
              placeholder="Expected hash"
              aria-label="Expected hash"
              className="mb-4 w-full rounded-lg border border-line bg-elevated px-3 py-2 font-mono text-xs text-ink placeholder:text-ink-faint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setVerifyHashPrompt(null)}
                className="min-h-9 rounded-lg border border-line bg-elevated px-3.5 text-sm text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!verifyHashInput.trim()}
                onClick={() => {
                  const { file, algorithm } = verifyHashPrompt;
                  setVerifyHashPrompt(null);
                  void runHashVerification(file, algorithm, verifyHashInput);
                }}
                className="min-h-9 rounded-lg border border-transparent bg-indigo-600 px-4 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
              >
                Verify
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Camera Barcode Scanner Modal */}
      <CameraBarcodeModal
        isOpen={showCameraScanner}
        onClose={() => setShowCameraScanner(false)}
        onDetected={handleCameraDetected}
      />

      {/* Delete confirmation (in-app; window.confirm is a webview no-op) */}
      <ConfirmDialog
        isOpen={Boolean(pendingDeleteFile)}
        title="Delete file"
        message={`Delete this file?\n\n${pendingDeleteFile?.path ?? ""}\n\nThis action cannot be undone.`}
        confirmLabel="Delete"
        danger
        onConfirm={confirmDeleteFile}
        onCancel={() => setPendingDeleteFile(null)}
      />

      {/* LAN access modal (issues #197/#198/#199) — one modal for both
          directions; it stays open through the rebind and reports inline. */}
      <LanModal
        open={lanModalOpen}
        systemInfo={systemInfo}
        showToast={showToast}
        onConfirmed={setSystemInfo}
        onClose={() => setLanModalOpen(false)}
      />

      {/* Single Match Launch Confirmation */}
      <SingleMatchPromptModal
        isOpen={Boolean(singleMatchFile)}
        file={singleMatchFile}
        onConfirm={() => {
          if (singleMatchFile) {
            const f = singleMatchFile;
            setSingleMatchFile(null);
            handleLaunch(f);
          }
        }}
        onDismiss={() => setSingleMatchFile(null)}
      />

      {/* Command palette (issue #224) — every command, one surface */}
      <CommandPalette
        isOpen={showCommandPalette}
        onClose={() => setShowCommandPalette(false)}
        commands={commands}
        files={scan.files}
        onOpenFile={(file) => void handleLaunch(file)}
        recentIds={recentIds}
        onCommandUsed={touchRecentCommand}
      />

      {/* Command-line arguments before a launch (context menu, command
          palette). Submitting closes the menu it came from, as before. */}
      <LaunchArgsDialog
        open={argsFile !== null}
        filename={argsFile?.filename ?? ""}
        onClose={() => setArgsFile(null)}
        onSubmit={(args) => {
          const file = argsFile;
          setArgsFile(null);
          setContextMenuPos(null);
          if (file) void handleLaunch(file, args);
        }}
      />

    </div>
  );
}
