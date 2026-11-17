import { useEffect, useMemo, useRef, useState } from "react";
import {
  computeHash,
  fetchConfig,
  fetchSystemInfo,
  launchFile,
  openFolder,
  openLogFile,
  openTerminal,
  revealFile,
  selectDirectory,
  browseDirectory,
  loadConfigContent,
  reloadConfig,
  exportCsvToDisk,
  setLanEnabled,
  waitForLanState,
} from "./api/client";
import type { AppConfigData, ScannedFileItem, SystemInfo } from "./api/types";
import {
  nextDragState,
  pickConfigFile,
  resetDragState,
  type DragTrackerState,
} from "./utils/configDrop";
import { resolveSessionTheme } from "./utils/theme";
import { mergeDirectoryPreference } from "./utils/scanDefaults";
import { useScanController } from "./hooks/useScanController";
import { useToast } from "./hooks/useToast";
import { useExternalEvents } from "./hooks/useExternalEvents";
import { useGlobalShortcuts } from "./hooks/useGlobalShortcuts";
import { useAutoRescanTimer } from "./hooks/useAutoRescanTimer";
import { useBarcodeMode } from "./hooks/useBarcodeMode";
import { useTheme } from "./hooks/useTheme";
import { ActionBar } from "./components/ActionBar";
import { ConfigEditorModal } from "./components/ConfigEditorModal";
import { ContextMenu, type ContextMenuPosition } from "./components/ContextMenu";
import { DirectoryPickerModal } from "./components/DirectoryPickerModal";
import { DropConfigOverlay } from "./components/DropConfigOverlay";
import { FileListTable } from "./components/FileListTable";
import { HeaderBar } from "./components/HeaderBar";
import { InitErrorPanel } from "./components/InitErrorPanel";
import { SearchBar } from "./components/SearchBar";
import { LogViewerModal } from "./components/LogViewerModal";
import { ShortcutsModal } from "./components/ShortcutsModal";
import { LoadConfigModal } from "./components/LoadConfigModal";
import { FilePropertiesModal } from "./components/FilePropertiesModal";
import { BarcodeModal } from "./components/BarcodeModal";
import { CameraBarcodeModal } from "./components/CameraBarcodeModal";
import { SingleMatchPromptModal } from "./components/SingleMatchPromptModal";
import { StatusBar } from "./components/StatusBar";
import { TimerModal } from "./components/TimerModal";
import { WorkflowRunnerModal } from "./components/WorkflowRunnerModal";
import { ConfirmDialog } from "./components/ConfirmDialog";
import { CopyableUrl } from "./components/CopyableUrl";
import { exportToCsv } from "./utils/exportCsv";
import { matchFilter } from "./utils/searchSyntax";

/** Debounce for the client-side prefilter derivation while typing (lane #1). */
const PREFILTER_DEBOUNCE_MS = 120;

export default function App() {
  const { theme, applyTheme, toggleTheme } = useTheme();
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [config, setConfig] = useState<AppConfigData | null>(null);
  const [activeDirectory, setActiveDirectory] = useState<string>("");
  const [activeExtension, setActiveExtension] = useState<string>("");
  const [filterText, setFilterText] = useState<string>("");
  const [recursive, setRecursive] = useState<boolean>(true);

  /** Reason the initial load failed, when it did — drives the retry panel. */
  const [initError, setInitError] = useState<string | null>(null);
  const [initRetrying, setInitRetrying] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);

  // Bluetooth-free prefilter — the perceptibly-instant client-side list.
  // The query applied to the list lags the input by ~120ms so a burst of
  // keystrokes only re-derives the filter once (see lane #1).
  const [prefilterQuery, setPrefilterQuery] = useState("");

  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [showShortcuts, setShowShortcuts] = useState<boolean>(false);
  const { toastMessage, showToast, dismissToast } = useToast();
  const [reloading, setReloading] = useState<boolean>(false);
  const [language, setLanguage] = useState<"en" | "fr">("en");
  const [showDirPicker, setShowDirPicker] = useState<boolean>(false);
  const [showConfigPicker, setShowConfigPicker] = useState<boolean>(false);
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
  /** Pending LAN toggle (true/false) awaiting user confirmation. */
  const [lanPending, setLanPending] = useState<boolean | null>(null);

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

  /** Open the in-app confirmation dialog for a LAN toggle request. */
  const toggleLan = (next: boolean) => {
    setLanPending(next);
  };

  /**
   * Path of the currently selected row. Selection is re-anchored by path when
   * the visible (filtered) set changes, so it never silently drifts onto an
   * unrelated file.
   */
  const selectedPathRef = useRef<string | null>(null);

  /**
   * Current search-bar state as scan parameters — the single source shared
   * by the scan controller and the barcode hook (issue #148 PR 4).
   */
  const getScanParams = () => ({ directory: activeDirectory, extension: activeExtension, filter_text: filterText, recursive });

  /**
   * Scan orchestration (issue #148): list state, the generation protocol,
   * the deferred server auto-rescan, sort reloads and paging live in the
   * hook. App keeps the UI-side concerns — toasts (showToast) and selection
   * (a fresh result set is authoritative, so onFreshResults re-anchors it).
   */
  const scan = useScanController({
    showToast,
    getScanParams,
    onFreshResults: () => {
      // Reset the selection anchor; a fresh result set is authoritative.
      selectedPathRef.current = null;
      setSelectedIndex(0);
    },
  });

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
    onApplyValues: (values) => {
      if (values.filter !== undefined) setFilterText(values.filter);
      if (values.ext !== undefined) setActiveExtension(values.ext);
      if (values.recursive !== undefined) setRecursive(values.recursive);
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
        : scan.files.filter((f) => matchFilter(f.rel_path, prefilterQuery)),
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

  // Selection reconcile: when a new visible set arrives, follow the previously
  // selected file (matched by path) if it is still visible — even though its
  // index moved — otherwise clamp into the shrunken set.
  useEffect(() => {
    const queryPath = selectedPathRef.current;
    const followed = queryPath
      ? visibleFiles.findIndex((f) => f.path === queryPath)
      : -1;
    if (followed >= 0) {
      setSelectedIndex((prev) => (followed !== prev ? followed : prev));
      return;
    }
    setSelectedIndex((prev) => Math.min(prev, Math.max(0, visibleFiles.length - 1)));
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
      setRecursive(cfg.recursive_search);

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
          recursive: cfg.recursive_search,
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
    setRecursive(cfg.recursive_search);

    if (!cfg.session_trial) {
      showToast(cfg.config_exists ? `Loaded config: ${cfg.config_path}` : "Starter configuration created.");
    }
    if (targetDirectory) {
      await scan.scanWithGeneration(scanGeneration, {
        directory: targetDirectory,
        extension: nextExtension,
        filter_text: nextFilter,
        recursive: cfg.recursive_search,
      }, { errorPrefix: "Scan failed after config load" });
    } else {
      scan.finishScan(scanGeneration);
    }
  };

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
      await handleConfigLoaded(cfg);
      showToast(`Session config applied: ${file.name}`);
    } catch (err: any) {
      showToast(err.message || "Failed to apply dropped configuration", "error");
    }
  };
  dropHandlerRef.current = (file: File) => {
    void handleDroppedConfig(file);
  };

  // Config handoff notifications (issue #4) — the poll lives in the hook;
  // App injects the re-apply (fresh config + handleConfigLoaded) and the toast.
  useExternalEvents({
    onConfigApplied: async () => {
      const cfg = await fetchConfig();
      await handleConfigLoaded(cfg);
    },
    showToast,
  });

  useEffect(() => {
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
        if (files.length > 0) showToast("Not a ProFiles configuration file.", "error");
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
      recursive,
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
    if (cfg.recursive_search !== undefined) setRecursive(cfg.recursive_search);
    if (initialFilter) setFilterText(initialFilter);
    if (!cfg.config_exists) {
      setShowConfigPicker(true);
    }

    if (initialDir) {
      try {
        await scan.runScan(scanGeneration, {
          directory: initialDir,
          extension: initialExt,
          filter_text: initialFilter,
          recursive: cfg.recursive_search,
        });
      } catch (scanErr: any) {
        if (scan.isCurrentScan(scanGeneration)) showToast(`Initial scan failed: ${scanErr.message}`, "error");
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
        recursive,
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
      { directory: activeDirectory, extension: activeExtension, filter_text: filterText, recursive },
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
   * Recursive checkbox handler (SearchBar). Applies the new value to
   * state, then schedules the same deferred server auto-rescan as the
   * filter input — so toggling the checkbox rescans immediately instead
   * of waiting for the next explicit scan.
   */
  const handleRecursiveToggle = (next: boolean) => {
    setRecursive(next);
    scan.scheduleDeferredRescan();
  };

  /**
   * Extension combobox handler (SearchBar). The server already scanned with
   * the previous extension, so a change must rescan — the same deferred
   * auto-rescan as the filter input and recursive checkbox (issue #122).
   */
  const handleExtensionChange = (ext: string) => {
    setActiveExtension(ext);
    scan.scheduleDeferredRescan();
  };

  const handleClearFilter = async () => {
    setFilterText("");
    await scan.scanWith(
      { directory: activeDirectory, extension: activeExtension, filter_text: "", recursive },
      { errorPrefix: "Scan failed" },
    );
  };

  /** Re-run the scan with recursive subdirectories turned off (empty-state action). */
  const handleDisableRecursive = async () => {
    setRecursive(false);
    await scan.scanWith(
      { directory: activeDirectory, extension: activeExtension, filter_text: filterText, recursive: false },
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

  // Context menu actions
  const handleLaunchWithArgs = async (file: ScannedFileItem, args: string) => {
    handleLaunch(file, args);
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
      { directory: activeDirectory, extension: activeExtension, filter_text: folder, recursive },
      { errorPrefix: "Scan failed" },
    );
  };

  const handleFilterExtension = (ext: string) => {
    setActiveExtension(ext);
    void scan.scanWith(
      { directory: activeDirectory, extension: ext, filter_text: filterText, recursive },
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
      const uri = new URL("file:///").href + file.path.replace(/\\/g, "/");
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
      showShortcuts ||
      showDirPicker ||
      showConfigPicker ||
      showPropertiesModal ||
      showLogViewer ||
      showTimerModal ||
      showBarcodeModal ||
      showCameraScanner ||
      singleMatchFile ||
      workflowLaunchParams ||
      Boolean(pendingDeleteFile),
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
  const onEscape = () => {
    setContextMenuPos(null);
    setShowShortcuts(false);
    setShowLogViewer(false);
    setShowTimerModal(false);
    // Cancelled drags may never fire dragleave (WKWebView) — make
    // Escape a hard reset for the drop overlay.
    applyDragState(resetDragState());
  };
  useGlobalShortcuts({
    anyModalOpen, visibleFiles, selectedIndex,
    activeDirectory, activeExtension, filterText, recursive, barcodeMode,
    onEscape,
    onContextMenu: setContextMenuPos,
    onExecute: handleExecute,
    onScan: handleScan,
    onReloadConfig: handleReloadConfig,
    onGoHome: handleGoToHomeDirectory,
    onProperties: handleProperties,
    onToggleTheme: () => toggleTheme({ persist: true }),
    setShowLogViewer, setShowShortcuts, setShowTimerModal,
    setShowConfigEditor, setBarcodeMode, setShowCameraScanner,
    moveSelection,
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
        recursive={recursive}
        onRecursiveChange={handleRecursiveToggle}
        onScan={handleScan}
        scanning={scan.scanning}
        barcodeMode={barcodeMode}
        onBarcodeToggle={handleBarcodeToggle}
        onCameraBarcodeClick={() => setShowCameraScanner(true)}
        autoRescanActive={autoRescanInterval > 0}
        onTimerClick={() => setShowTimerModal(true)}
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
          recursive={recursive}
          onDisableRecursive={handleDisableRecursive}
          onOpenDirectory={handleOpenActiveDirectory}
          onLoadConfig={() => setShowConfigPicker(true)}
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
        // Repurposed (issue #95): opens the in-app YAML editor. The OS-launch
        // this button used to perform now lives in the editor's header
        // ("Open in OS"); the modal's onApplied drives handleConfigLoaded,
        // the same refresh path as LoadConfigModal and the drag/drop trial.
        // Config LOADING no longer lives here (issue #101): the editor's
        // "Load config file…" raises the picker from inside the editor.
        onOpenConfig={() => setShowConfigEditor(true)}
        onShowShortcuts={() => setShowShortcuts(true)}
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
        onLoadConfig={() => setShowConfigPicker(true)}
        reloadKey={editorReloadKey}
      />

      {/* Config Picker Modal. onLoaded ALSO bumps the editor's reload key
          so an editor left open underneath re-fetches the freshly picked
          file instead of keeping stale text (issue #101). */}
      <LoadConfigModal
        isOpen={showConfigPicker}
        activeConfigPath={config?.config_path}
        configExists={config?.config_exists}
        onClose={() => setShowConfigPicker(false)}
        onLoaded={(cfg) => {
          void handleConfigLoaded(cfg);
          setEditorReloadKey((key) => key + 1);
        }}
      />

      {/* Dropped configuration files (session-only trial) */}
      <DropConfigOverlay
        visible={dropOverlayVisible}
        onFileSelected={(file) => dropHandlerRef.current(file)}
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
        onLaunchWithArgs={handleLaunchWithArgs}
        onReveal={handleReveal}
        onOpenFolder={handleOpenFolder}
        onOpenTerminal={handleOpenTerminal}
        onScanDirectory={handleScanDirectory}
        onFilterFolder={handleFilterFolder}
        onFilterExtension={handleFilterExtension}
        onCopyPath={handleCopyPath}
        onCopyFilename={handleCopyFilename}
        onCopyUri={handleCopyUri}
        onComputeHash={handleComputeHash}
        onVerifyHash={handleVerifyHash}
        onProperties={handleProperties}
        onClearFile={handleClearFile}
        onGenerateBarcode={handleGenerateBarcode}
        showToast={showToast}
      />

      {/* Shortcuts Modal */}
      <ShortcutsModal isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />

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
        onSetInterval={handleTimerSet}
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

      {/* LAN toggle confirmation */}
      <ConfirmDialog
        isOpen={lanPending !== null}
        title={lanPending ? "Enable LAN access?" : "Restrict to this machine?"}
        message={
          lanPending ? (
            <span className="block">
              ProFiles will be reachable by anyone on this network:
              <CopyableUrl
                url={`http://${systemInfo?.hostname}:${window.location.port}`}
                label="Copy hostname URL"
                className="mt-1.5"
                onCopied={() => showToast("URL copied to clipboard.")}
                onCopyError={() => showToast("Failed to copy URL.", "error")}
              />
              <CopyableUrl
                url={`http://${systemInfo?.ip}:${window.location.port}`}
                label="Copy IP URL"
                className="mt-1.5"
                onCopied={() => showToast("URL copied to clipboard.")}
                onCopyError={() => showToast("Failed to copy URL.", "error")}
              />
            </span>
          ) : (
            "ProFiles will be reachable only on this machine."
          )
        }
        confirmLabel={lanPending ? "Enable LAN" : "Restrict"}
        onConfirm={async () => {
          const next = lanPending!;
          setLanPending(null);
          try {
            await setLanEnabled(next);
            showToast(
              next
                ? "Updating LAN binding…"
                : "Restricting ProFiles to this machine…",
              "info"
            );
            // The rebind runs after the response; observe the real outcome.
            const sys = await waitForLanState(next);
            if (sys) setSystemInfo(sys);
            if (sys?.lan_enabled === next) {
              showToast(
                next
                  ? "ProFiles is now reachable on the local network."
                  : "ProFiles is restricted to this machine.",
                "info"
              );
            } else {
              showToast(
                "Failed to update LAN binding — the previous address is still active.",
                "error"
              );
            }
          } catch (err) {
            const msg = err instanceof Error ? err.message : "Failed to update LAN binding";
            showToast(`Failed to update LAN binding: ${msg}`, "error");
            // Refetch to restore the actual state
            const sys = await fetchSystemInfo();
            setSystemInfo(sys);
          }
        }}
        onCancel={() => setLanPending(null)}
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

    </div>
  );
}
