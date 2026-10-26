import { useEffect, useMemo, useRef, useState } from "react";
import {
  computeHash,
  executeScan,
  fetchConfig,
  fetchNotifications,
  fetchScanResults,
  fetchSystemInfo,
  launchFile,
  openConfigFile,
  openFolder,
  openLogFile,
  openTerminal,
  revealFile,
  selectDirectory,
  browseDirectory,
  loadConfigContent,
  reloadConfig,
  exportCsvToDisk,
} from "./api/client";
import type { AppConfigData, ExternalEvent, ScanSort, ScannedFileItem, SystemInfo } from "./api/types";
import {
  nextDragState,
  pickConfigFile,
  resetDragState,
  type DragTrackerState,
} from "./utils/configDrop";
import { resolveSessionTheme } from "./utils/theme";
import { ActionBar } from "./components/ActionBar";
import { ContextMenu, type ContextMenuPosition } from "./components/ContextMenu";
import { DirectoryPickerModal } from "./components/DirectoryPickerModal";
import { DropConfigOverlay } from "./components/DropConfigOverlay";
import { FileListTable, SCAN_PAGE_SIZE } from "./components/FileListTable";
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
import { parseBarcodeInput } from "./utils/barcodeScanner";
import { exportToCsv } from "./utils/exportCsv";
import { matchFilter } from "./utils/searchSyntax";

/** Debounce for the client-side prefilter derivation while typing (lane #1). */
const PREFILTER_DEBOUNCE_MS = 120;
/** Debounce for the deferred server auto-rescan after the last filter keystroke. */
const AUTO_RESCAN_DEBOUNCE_MS = 800;
/** Poll interval for server-side UI events (config handoff toasts). */
const NOTIFICATION_POLL_MS = 4000;

export default function App() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [config, setConfig] = useState<AppConfigData | null>(null);
  const [activeDirectory, setActiveDirectory] = useState<string>("");
  const [activeExtension, setActiveExtension] = useState<string>("");
  const [filterText, setFilterText] = useState<string>("");
  const [recursive, setRecursive] = useState<boolean>(true);

  const [files, setFiles] = useState<ScannedFileItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [hasScanned, setHasScanned] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  /** Reason the initial load failed, when it did — drives the retry panel. */
  const [initError, setInitError] = useState<string | null>(null);
  const [initRetrying, setInitRetrying] = useState(false);
  /** Column the list is ordered by, or `null` for scan order. */
  const [sort, setSort] = useState<ScanSort | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [scanning, setScanning] = useState<boolean>(false);
  const scanGenerationRef = useRef(0);
  /** Controller for the current generation's scan fetches; aborted when superseded. */
  const scanAbortRef = useRef<AbortController | null>(null);
  /** Timeout id of the deferred server auto-rescan scheduled on filter typing. */
  const pendingAutoRescanRef = useRef<NodeJS.Timeout | null>(null);

  // Bluetooth-free prefilter — the perceptibly-instant client-side list.
  // The query applied to the list lags the input by ~120ms so a burst of
  // keystrokes only re-derives the filter once (see lane #1).
  const [prefilterQuery, setPrefilterQuery] = useState("");

  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [showShortcuts, setShowShortcuts] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<{ message: string; kind: "info" | "error" } | null>(null);
  const [reloading, setReloading] = useState<boolean>(false);
  const [language, setLanguage] = useState<"en" | "fr">("en");
  const [showDirPicker, setShowDirPicker] = useState<boolean>(false);
  const [showConfigPicker, setShowConfigPicker] = useState<boolean>(false);
  const [showPropertiesModal, setShowPropertiesModal] = useState<boolean>(false);
  const [propertiesFile, setPropertiesFile] = useState<ScannedFileItem | null>(null);
  const [showLogViewer, setShowLogViewer] = useState<boolean>(false);
  const [showTimerModal, setShowTimerModal] = useState<boolean>(false);

  // Workflow Modal state
  const [workflowLaunchParams, setWorkflowLaunchParams] = useState<{
    file: ScannedFileItem;
    args?: string;
  } | null>(null);

  // Barcode scanner mode — when active, the next Enter-terminated
  // keypress sequence is captured as barcode input.
  const [barcodeMode, setBarcodeMode] = useState<boolean>(false);
  const barcodeBufferRef = useRef<string>("");

  // QR code modal — shows a generated QR for sharing a file location.
  const [showBarcodeModal, setShowBarcodeModal] = useState<boolean>(false);
  const [barcodeFilePath, setBarcodeFilePath] = useState<string | undefined>(undefined);

  // Camera Barcode Scanner & Single match prompt state
  const [showCameraScanner, setShowCameraScanner] = useState<boolean>(false);
  const [singleMatchFile, setSingleMatchFile] = useState<ScannedFileItem | null>(null);

  // Timer — periodic rescan interval in seconds (0 = disabled).
  const [autoRescanInterval, setAutoRescanInterval] = useState<number>(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const toastTimerRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Show a transient toast above the action bar.
   *
   * Info toasts auto-dismiss after 3.5s; error toasts stay a little longer and
   * carry an inline dismiss button, so they never vanish before being read.
   */
  const showToast = (msg: string, kind: "info" | "error" = "info") => {
    if (!msg) return; // never blank an existing toast with an empty message
    setToastMessage({ message: msg, kind });
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(
      () => setToastMessage(null),
      kind === "error" ? 10000 : 3500,
    );
  };

  const dismissToast = () => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToastMessage(null);
  };

  const beginScan = () => {
    // Collision rule: any explicit scan (Enter, Scan button, programmatic
    // filter change, barcode apply…) supersedes a pending deferred
    // auto-rescan so the two never double-scan.
    if (pendingAutoRescanRef.current) {
      clearTimeout(pendingAutoRescanRef.current);
      pendingAutoRescanRef.current = null;
    }
    // Abort superseded in-flight scan fetches from the previous generation.
    scanAbortRef.current?.abort();
    scanAbortRef.current = new AbortController();
    const generation = ++scanGenerationRef.current;
    setScanning(true);
    setLoadingMore(false);
    return generation;
  };

  const isCurrentScan = (generation: number) => generation === scanGenerationRef.current;

  const finishScan = (generation: number) => {
    if (isCurrentScan(generation)) setScanning(false);
  };

  /**
   * Path of the currently selected row. Selection is re-anchored by path when
   * the visible (filtered) set changes, so it never silently drifts onto an
   * unrelated file.
   */
  const selectedPathRef = useRef<string | null>(null);

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
        ? files
        : files.filter((f) => matchFilter(f.rel_path, prefilterQuery)),
    [files, prefilterQuery],
  );

  /**
   * Coverage hint (lane #1): the loaded page is smaller than the backend's
   * full result set, so the prefilter only describes part of it — point the
   * user at the full server search (Enter).
   */
  const prefilterNote =
    filterText.trim() && files.length < totalCount
      ? `Prefiltering loaded results — press Enter to search all ${totalCount}`
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

  /**
   * Fetch the first page of scan results and replace the list.
   * Paging keeps the JSON payload small (500 rows instead of 25k+).
   *
   * @param sortOrder Sort to request; defaults to the current component state.
   *   Callers that just changed the sort must pass the new value, because the
   *   state update will not have been applied yet.
   */
  const loadScanResults = async (generation: number, sortOrder: ScanSort | null = sort) => {
    const res = await fetchScanResults({
      offset: 0,
      limit: SCAN_PAGE_SIZE,
      sort_by: sortOrder?.column,
      sort_dir: sortOrder?.direction,
      signal: scanAbortRef.current?.signal,
    });
    if (!isCurrentScan(generation)) return false;
    setFiles(res.items);
    setTotalCount(res.count);
    setHasScanned(true);
    return true;
  };

  const runScan = async (
    generation: number,
    params: Parameters<typeof executeScan>[0],
  ) => {
    if (!isCurrentScan(generation)) return false;
    await executeScan(params, scanAbortRef.current?.signal);
    if (!isCurrentScan(generation) || !(await loadScanResults(generation))) return false;
    // Fresh authoritative results — selection restarts at the top.
    selectedPathRef.current = null;
    setSelectedIndex(0);
    return true;
  };

  /** Fetch the next page and append it to the list. */
  const handleLoadMore = async () => {
    if (loadingMore || files.length >= totalCount) return;
    const generation = scanGenerationRef.current;
    setLoadingMore(true);
    try {
      const res = await fetchScanResults({
        offset: files.length,
        limit: SCAN_PAGE_SIZE,
        sort_by: sort?.column,
        sort_dir: sort?.direction,
      });
      if (!isCurrentScan(generation)) return;
      // Guard against duplicated rows if the cache changed mid-request.
      const existing = new Set(files.map((f) => f.path || f.filename));
      setFiles((prev) => [...prev, ...res.items.filter((f) => !existing.has(f.path || f.filename))]);
      setTotalCount(res.count);
    } catch {
      // Paging failure is non-fatal; retry happens on the next scroll attempt.
      showToast("Couldn't load more results — scroll to try again.", "error");
    } finally {
      if (isCurrentScan(generation)) setLoadingMore(false);
    }
  };

  const handleReloadConfig = async () => {
    if (reloading) return;
    setReloading(true);
    showToast("Reloading configuration...");

    const scanGeneration = beginScan();

    try {
      // 1. Fetch fresh system info (in case hostname/IP changed)
      const sys = await fetchSystemInfo();
      setSystemInfo(sys);

      // 2. Ask the server to re-parse the attached config file from disk
      //    (GET /api/config only returns the in-memory snapshot).
      const cfg = await reloadConfig();
      setConfig(cfg);

      // Theme from the freshly loaded config, like handleConfigLoaded does.
      setTheme(resolveSessionTheme(cfg.theme));

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
        await runScan(scanGeneration, {
          directory: targetDirectory,
          extension: nextExtension,
          filter_text: nextFilter,
          recursive: cfg.recursive_search,
        });
      }
    } catch (err: any) {
      showToast(`Failed to reload configuration: ${err.message}`, "error");
    } finally {
      setReloading(false);
      // Finish scan if it's still the current generation
      finishScan(scanGeneration);
    }
  };

  const handleConfigLoaded = async (cfg: AppConfigData) => {
    const scanGeneration = beginScan();
    setConfig(cfg);
    // Session-only configs apply their theme to the running session but
    // must NOT persist it (no localStorage write — that would leak the
    // trial into the next session).
    setTheme(resolveSessionTheme(cfg.theme));
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
      try {
        await runScan(scanGeneration, {
          directory: targetDirectory,
          extension: nextExtension,
          filter_text: nextFilter,
          recursive: cfg.recursive_search,
        });
      } catch (err: any) {
        showToast(`Scan failed after config load: ${err.message}`, "error");
      } finally {
        finishScan(scanGeneration);
      }
    } else {
      finishScan(scanGeneration);
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

  // Config handoff notifications (issue #4): when a second ProFiles launch
  // double-clicks a .profiles file, the running instance applies it
  // server-side and buffers an event. A light poll surfaces the event as a
  // toast and re-fetches the config + rescans when the event says one was
  // applied. Refs keep the interval callback reading the latest handlers.
  const lastEventIdRef = useRef(0);
  const externalConfigApplyRef = useRef<() => Promise<void>>(async () => {});
  useEffect(() => {
    externalConfigApplyRef.current = async () => {
      const cfg = await fetchConfig();
      await handleConfigLoaded(cfg);
    };
  });
  useEffect(() => {
    const poll = async () => {
      let events: ExternalEvent[] = [];
      try {
        const res = await fetchNotifications(lastEventIdRef.current);
        events = res.events;
      } catch {
        return; // server unreachable — retry silently on the next tick
      }
      for (const evt of events) {
        lastEventIdRef.current = Math.max(lastEventIdRef.current, evt.id);
        if (evt.config_applied) {
          try {
            await externalConfigApplyRef.current();
          } catch {
            // Re-applying is best-effort; the toast still explains what happened.
          }
        }
        showToast(evt.message);
      }
    };
    const id = setInterval(() => void poll(), NOTIFICATION_POLL_MS);
    return () => clearInterval(id);
  }, []);

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
    const scanGeneration = beginScan();
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
    if (!isCurrentScan(scanGeneration)) return;
    const nextExtension = directoryConfig?.extensions.includes(activeExtension)
      ? activeExtension
      : (directoryConfig?.extensions[0] ?? activeExtension);
    const nextFilter = directoryConfig?.filters.includes(filterText)
      ? filterText
      : (directoryConfig?.filters[0] ?? filterText);
    setActiveExtension(nextExtension);
    setFilterText(nextFilter);
    // Scan with the freshly picked directory
    try {
      await runScan(scanGeneration, {
        directory,
        extension: nextExtension,
        filter_text: nextFilter,
        recursive,
      });
    } catch (err: any) {
      if (isCurrentScan(scanGeneration)) showToast(`Scan failed: ${err.message}`, "error");
    } finally {
      finishScan(scanGeneration);
    }
  };

  const initializeFromConfig = async (cfg: AppConfigData, scanGeneration: number) => {
    if (!isCurrentScan(scanGeneration)) return;
    
    // Apply theme from .profiles configuration with highest priority
    // This overrides any localStorage value to ensure config file is the source of truth
    const configTheme = cfg.theme === "auto" ? "dark" : (cfg.theme === "light" ? "light" : "dark");
    setTheme(configTheme);
    
    // Persist the config theme to localStorage for future sessions
    try {
      localStorage.setItem("profiles-theme", configTheme);
    } catch {
      /* storage may be unavailable */
    }
    
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
        await runScan(scanGeneration, {
          directory: initialDir,
          extension: initialExt,
          filter_text: initialFilter,
          recursive: cfg.recursive_search,
        });
      } catch (scanErr: any) {
        if (isCurrentScan(scanGeneration)) showToast(`Initial scan failed: ${scanErr.message}`, "error");
      }
    }
  };

  // Initial load (also re-run by the retry panel when it fails).
  const runInitialLoad = async () => {
    const scanGeneration = ++scanGenerationRef.current;
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

  // Teardown: drop any pending deferred rescan and abort in-flight scan fetches.
  useEffect(
    () => () => {
      if (pendingAutoRescanRef.current) {
        clearTimeout(pendingAutoRescanRef.current);
        pendingAutoRescanRef.current = null;
      }
      scanAbortRef.current?.abort();
    },
    [],
  );

  // Directory change handler
  const handleDirectoryChange = async (newDir: string) => {
    const scanGeneration = beginScan();
    setActiveDirectory(newDir);
    try {
      const directoryConfig = await selectDirectory(newDir);
      if (!isCurrentScan(scanGeneration)) return;
      setConfig(directoryConfig);
      const nextExtension = directoryConfig.extensions.includes(activeExtension)
        ? activeExtension
        : (directoryConfig.extensions[0] ?? "");
      const nextFilter = directoryConfig.filters.includes(filterText)
        ? filterText
        : (directoryConfig.filters[0] ?? "");
      setActiveExtension(nextExtension);
      setFilterText(nextFilter);
      await runScan(scanGeneration, {
        directory: newDir,
        extension: nextExtension,
        filter_text: nextFilter,
        recursive,
      });
    } catch (err: any) {
      if (isCurrentScan(scanGeneration)) showToast(`Directory change failed: ${err.message}`, "error");
    } finally {
      finishScan(scanGeneration);
    }
  };

  // Run scan
  const handleScan = async () => {
    if (!activeDirectory) return;
    const scanGeneration = beginScan();
    try {
      await runScan(scanGeneration, {
        directory: activeDirectory,
        extension: activeExtension,
        filter_text: filterText,
        recursive,
      });
    } catch (err) {
      if (isCurrentScan(scanGeneration)) console.error("Scan error:", err);
    } finally {
      finishScan(scanGeneration);
    }
  };

  // Latest handleScan for deferred callbacks (avoids stale closures above).
  const handleScanRef = useRef(handleScan);
  useEffect(() => {
    handleScanRef.current = handleScan;
  });

  /**
   * Filter input handler (SearchBar onChange). Applies the text instantly
   * for the client-side prefilter, and schedules the deferred server
   * auto-rescan 800ms after the last keystroke. Enter/Scan clicks and
   * programmatic filter changes cancel the pending rescan from beginScan —
   * the explicit scan wins.
   */
  const handleFilterTextChange = (text: string) => {
    setFilterText(text);
    if (pendingAutoRescanRef.current) clearTimeout(pendingAutoRescanRef.current);
    pendingAutoRescanRef.current = setTimeout(() => {
      pendingAutoRescanRef.current = null;
      void handleScanRef.current();
    }, AUTO_RESCAN_DEBOUNCE_MS);
  };

  /**
   * Recursive checkbox handler (SearchBar). Applies the new value to
   * state, then schedules the same deferred server auto-rescan as the
   * filter input — so toggling the checkbox rescans immediately instead
   * of waiting for the next explicit scan. Rapid toggles are
   * race-correct: beginScan cancels any pending deferred rescan, so the
   * explicit scan always wins, and the timer callback reads the latest
   * recursive state via handleScanRef.
   */
  const handleRecursiveToggle = (next: boolean) => {
    setRecursive(next);
    if (pendingAutoRescanRef.current) clearTimeout(pendingAutoRescanRef.current);
    pendingAutoRescanRef.current = setTimeout(() => {
      pendingAutoRescanRef.current = null;
      void handleScanRef.current();
    }, AUTO_RESCAN_DEBOUNCE_MS);
  };

  const handleClearFilter = async () => {
    setFilterText("");
    if (!activeDirectory) return;
    const scanGeneration = beginScan();
    try {
      await runScan(scanGeneration, {
        directory: activeDirectory,
        extension: activeExtension,
        filter_text: "",
        recursive,
      });
    } catch (err) {
      if (isCurrentScan(scanGeneration)) console.error("Scan error:", err);
    } finally {
      finishScan(scanGeneration);
    }
  };

  /** Re-run the scan with recursive subdirectories turned off (empty-state action). */
  const handleDisableRecursive = async () => {
    setRecursive(false);
    if (!activeDirectory) return;
    const scanGeneration = beginScan();
    try {
      await runScan(scanGeneration, {
        directory: activeDirectory,
        extension: activeExtension,
        filter_text: filterText,
        recursive: false,
      });
    } catch (err: any) {
      if (isCurrentScan(scanGeneration)) showToast(`Scan failed: ${err.message}`, "error");
    } finally {
      finishScan(scanGeneration);
    }
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
    try {
      await handleDirectoryChange(directory);
      showToast(`Scanned directory: ${directory}`);
    } catch (err: any) {
      showToast(`Error: ${err.message}`, "error");
    }
  };

  const handleFilterFolder = (folder: string) => {
    setFilterText(folder);
    const scanGeneration = beginScan();
    void runScan(scanGeneration, {
      directory: activeDirectory,
      extension: activeExtension,
      filter_text: folder,
      recursive,
    }).catch((err) => {
      if (isCurrentScan(scanGeneration)) console.error("Scan error:", err);
    }).finally(() => finishScan(scanGeneration));
  };

  const handleFilterExtension = (ext: string) => {
    setActiveExtension(ext);
    const scanGeneration = beginScan();
    void runScan(scanGeneration, {
      directory: activeDirectory,
      extension: ext,
      filter_text: filterText,
      recursive,
    }).catch((err) => {
      if (isCurrentScan(scanGeneration)) console.error("Scan error:", err);
    }).finally(() => finishScan(scanGeneration));
  };

  const handleCopyPath = (file: ScannedFileItem, forwardSlash?: boolean) => {
    const p = forwardSlash ? file.path.replace(/\\/g, "/") : file.path;
    navigator.clipboard.writeText(p);
    showToast("Path copied to clipboard.");
  };

  const handleCopyFilename = (file: ScannedFileItem, withoutExt?: boolean) => {
    let name = file.filename;
    if (withoutExt) {
      const idx = name.lastIndexOf(".");
      if (idx !== -1) name = name.slice(0, idx);
    }
    navigator.clipboard.writeText(name);
    showToast("Filename copied to clipboard.");
  };

  const handleComputeHash = async (file: ScannedFileItem, algorithm: "md5" | "sha256") => {
    try {
      showToast(`Computing ${algorithm.toUpperCase()}...`);
      const res = await computeHash(file.path, algorithm);
      navigator.clipboard.writeText(res.hash);
      showToast(`${algorithm.toUpperCase()} hash copied: ${res.hash.slice(0, 12)}...`);
    } catch (err: any) {
      showToast(`Hash computation failed: ${err.message}`, "error");
    }
  };

  const handleCopyUri = async (file: ScannedFileItem) => {
    try {
      const uri = new URL("file:///").href + file.path.replace(/\\/g, "/");
      navigator.clipboard.writeText(uri);
      showToast("File URI copied to clipboard.");
    } catch (err: any) {
      showToast(`URI copy failed: ${err.message}`, "error");
    }
  };

  const handleVerifyHash = async (file: ScannedFileItem, algorithm: "md5" | "sha256") => {
    try {
      const clipboardText = await navigator.clipboard.readText();
      if (!clipboardText.trim()) {
        showToast("Clipboard is empty — copy a hash first, then try again.");
        return;
      }
      showToast(`Computing ${algorithm.toUpperCase()}...`);
      const res = await computeHash(file.path, algorithm);
      const match = res.hash.toLowerCase() === clipboardText.trim().toLowerCase();
      if (match) {
        showToast(`✅  ${algorithm.toUpperCase()} matches!`);
      } else {
        showToast(`❌  ${algorithm.toUpperCase()} mismatch`);
      }
    } catch (err: any) {
      showToast(`Verification failed: ${err.message}`, "error");
    }
  };

  const handleProperties = (file: ScannedFileItem) => {
    setPropertiesFile(file);
    setShowPropertiesModal(true);
  };

  const handleClearFile = async (file: ScannedFileItem) => {
    if (!confirm(`Are you sure you want to delete this file?\n\n${file.path}\n\nThis action cannot be undone.`)) {
      return;
    }
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
    if (files.length === 0) {
      showToast("No files to export.");
      return;
    }
    try {
      const csvContent = exportToCsv(files, config?.column_names || [], config ?? undefined, filterText);
      const filename = `profiles-export-${new Date().toISOString().slice(0, 19).replace(/[:.]/g, "-")}.csv`;
      // Saved server-side: browser blob downloads navigate to raw CSV inside the desktop webview.
      const result = await exportCsvToDisk(csvContent, filename);
      showToast(result.message);
    } catch (err: any) {
      showToast(`Export failed: ${err.message}`, "error");
    }
  };

  const handleCameraDetected = async (rawCode: string) => {
    setShowCameraScanner(false);
    showToast("Barcode detected!");

    const result = parseBarcodeInput(rawCode);
    const vals = result.values;

    const nextDir = vals.dir !== undefined ? vals.dir : activeDirectory;
    const nextExt = vals.ext !== undefined ? vals.ext : activeExtension;
    const nextFilter = vals.filter !== undefined ? vals.filter : filterText;
    const nextRecursive = vals.recursive !== undefined ? vals.recursive : recursive;

    if (vals.dir !== undefined) setActiveDirectory(vals.dir);
    if (vals.ext !== undefined) setActiveExtension(vals.ext);
    if (vals.filter !== undefined) setFilterText(vals.filter);
    if (vals.recursive !== undefined) setRecursive(vals.recursive);

    if (nextDir) {
      const scanGeneration = beginScan();
      try {
        await executeScan(
          {
            directory: nextDir,
            extension: nextExt,
            filter_text: nextFilter,
            recursive: nextRecursive,
          },
          scanAbortRef.current?.signal,
        );

        const res = await fetchScanResults({
          offset: 0,
          limit: SCAN_PAGE_SIZE,
          sort_by: sort?.column,
          sort_dir: sort?.direction,
          signal: scanAbortRef.current?.signal,
        });

        if (!isCurrentScan(scanGeneration)) return;

        setFiles(res.items);
        setTotalCount(res.count);
        setHasScanned(true);
        // Reset the selection anchor; a fresh result set is authoritative.
        selectedPathRef.current = null;
        setSelectedIndex(0);

        if (res.count === 1 && res.items.length === 1) {
          setSingleMatchFile(res.items[0]);
        }
      } catch (err: any) {
        // Aborted (superseded) camera scans stay silent.
        if (isCurrentScan(scanGeneration)) showToast(`Scan error: ${err.message}`, "error");
      } finally {
        finishScan(scanGeneration);
      }
    }
  };

  const handleBarcodeToggle = () => {
    setBarcodeMode((prev) => {
      const next = !prev;
      if (next) {
        barcodeBufferRef.current = "";
        showToast("Barcode mode ON — scan a barcode now.");
      } else {
        barcodeBufferRef.current = "";
        showToast("Barcode mode OFF.");
      }
      return next;
    });
  };

  const applyBarcodeValues = (values: Partial<{
    filter: string;
    ext: string;
    recursive: boolean;
    dir: string;
    scan: boolean;
  }>) => {
    if (values.filter !== undefined) setFilterText(values.filter);
    if (values.ext !== undefined) setActiveExtension(values.ext);
    if (values.recursive !== undefined) setRecursive(values.recursive);
    if (values.dir !== undefined) setActiveDirectory(values.dir);

    // If scan=1 or any value was applied, trigger a rescan
    const shouldScan = values.scan === true ||
      values.filter !== undefined ||
      values.ext !== undefined ||
      values.recursive !== undefined ||
      values.dir !== undefined;

    if (shouldScan) {
      // Disable barcode mode after applying
      setBarcodeMode(false);
      barcodeBufferRef.current = "";
      // Use a short timeout to let state propagate before scanning
      setTimeout(() => {
        void handleScan();
      }, 50);
    }
  };

  // Barcode scanner input — global keypress listener when barcodeMode is active.
  // USB/wedge scanners emit keystrokes + Enter; we accumulate until Enter.
  useEffect(() => {
    if (!barcodeMode) return;

    const handleKeydown = (e: KeyboardEvent) => {
      if (e.key === "Enter") {
        const raw = barcodeBufferRef.current;
        if (!raw) {
          barcodeBufferRef.current = "";
          return;
        }

        e.preventDefault();
        barcodeBufferRef.current = "";

        const result = parseBarcodeInput(raw);

        if (result.isPlainFilter) {
          showToast(`Barcode filter: ${result.values.filter}`);
          setFilterText(result.values.filter || "");
          setBarcodeMode(false);
          setTimeout(() => void handleScan(), 50);
        } else {
          // Parsed key=value pairs — apply all and auto-scan
          const vals = result.values;
          const summary = Object.entries(vals)
            .map(([k, v]) => `${k}=${v}`)
            .join(", ");
          showToast(`Barcode applied: ${summary}`);
          applyBarcodeValues(vals);
        }
      } else if (e.key === "Escape") {
        // Allow user to cancel barcode mode
        setBarcodeMode(false);
        barcodeBufferRef.current = "";
        showToast("Barcode mode cancelled.");
      } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
        // Accumulate printable characters
        barcodeBufferRef.current += e.key;
      }
    };

    document.addEventListener("keydown", handleKeydown, true);
    return () => document.removeEventListener("keydown", handleKeydown, true);
  }, [barcodeMode]);

  // Timer — periodic rescan effect.
  useEffect(() => {
    if (autoRescanInterval > 0) {
      timerRef.current = setInterval(() => {
        void handleScan();
      }, autoRescanInterval * 1000);
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [autoRescanInterval]);

  const handleTimerSet = (intervalSeconds: number) => {
    setAutoRescanInterval(intervalSeconds);
    if (intervalSeconds > 0) {
      showToast(`Auto-rescan every ${intervalSeconds}s.`);
    } else {
      showToast("Auto-rescan disabled.");
    }
  };

  // Keyboard navigation & global shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Allow Esc to close context menu or modals
      if (e.key === "Escape") {
        setContextMenuPos(null);
        setShowShortcuts(false);
        setShowLogViewer(false);
        setShowTimerModal(false);
        // Cancelled drags may never fire dragleave (WKWebView) — make
        // Escape a hard reset for the drop overlay.
        applyDragState(resetDragState());
        return;
      }

      if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        document.querySelector<HTMLElement>("[data-testid='file-list']")?.focus();
        return;
      }

      // If typing in input / select, handle Enter for scan
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) {
        if (e.key === "Enter") {
          handleScan();
        }
        return;
      }

      if (e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")) {
        const file = visibleFiles[selectedIndex];
        if (!file) return;
        e.preventDefault();
        const row = document.querySelector<HTMLElement>(`[data-row-index="${selectedIndex}"]`);
        const rect = row?.getBoundingClientRect();
        setContextMenuPos({
          x: rect ? rect.left + 24 : 24,
          y: rect ? rect.top + rect.height / 2 : 24,
          file,
        });
        return;
      }

      // F5: Refresh
      if (e.key === "F5") {
        e.preventDefault();
        handleScan();
        return;
      }

      // Ctrl + R: Reload config & scan
      if (e.ctrlKey && e.key.toLowerCase() === "r") {
        e.preventDefault();
        handleReloadConfig();
        return;
      }

      // Ctrl + D: Focus directory
      if (e.ctrlKey && e.key.toLowerCase() === "d") {
        e.preventDefault();
        const dirInput = document.querySelector("input[list='directories-list']") as HTMLInputElement | null;
        dirInput?.focus();
        return;
      }

      // Ctrl + E: Focus extension
      if (e.ctrlKey && e.key.toLowerCase() === "e") {
        e.preventDefault();
        const extInput = document.querySelector("input[list='extensions-list']") as HTMLInputElement | null;
        extInput?.focus();
        return;
      }

      // Ctrl + F: Focus filter
      if (e.ctrlKey && e.key.toLowerCase() === "f") {
        e.preventDefault();
        const filterInput = document.querySelector("input[placeholder*='Filter files']") as HTMLInputElement | null;
        filterInput?.focus();
        return;
      }

      // Ctrl + Shift + L: Open the log viewer
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        setShowLogViewer((prev) => !prev);
        return;
      }

      // Ctrl + ,: Open config
      if (e.ctrlKey && e.key === ",") {
        e.preventDefault();
        openConfigFile().then((r) => showToast(r.message));
        return;
      }

      // Ctrl + Shift + T: Cycle theme
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "t") {
        e.preventDefault();
        setTheme((prev) => (prev === "dark" ? "light" : "dark"));
        return;
      }

      // Ctrl + B: Toggle barcode scanner mode
      if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "b") {
        e.preventDefault();
        setBarcodeMode((prev) => !prev);
        return;
      }

      // Ctrl + Shift + B: Open camera barcode scanner
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "b") {
        e.preventDefault();
        setShowCameraScanner((prev) => !prev);
        return;
      }

      // Ctrl + T: Open timer modal
      if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "t") {
        e.preventDefault();
        setShowTimerModal(true);
        return;
      }

      // Ctrl + H: Go to home directory
      if (e.ctrlKey && !e.shiftKey && e.key.toLowerCase() === "h") {
        e.preventDefault();
        void handleGoToHomeDirectory();
        return;
      }

      // ? or Ctrl + /: Show shortcuts
      if (e.key === "?" || (e.ctrlKey && e.key === "/")) {
        e.preventDefault();
        setShowShortcuts((prev) => !prev);
        return;
      }

      // P: Open file properties (when a file is selected)
      if (e.key.toLowerCase() === "p" && !e.ctrlKey && !e.shiftKey && !e.altKey) {
        const file = visibleFiles[selectedIndex];
        if (file) {
          e.preventDefault();
          handleProperties(file);
        }
        return;
      }

      // Table navigation — indexed over the VISIBLE (filtered) rows.
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => {
          const next = Math.min(prev + 1, Math.max(0, visibleFiles.length - 1));
          selectedPathRef.current = visibleFiles[next]?.path ?? null;
          return next;
        });
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => {
          const next = Math.max(prev - 1, 0);
          selectedPathRef.current = visibleFiles[next]?.path ?? null;
          return next;
        });
      } else if (e.key === "Enter") {
        e.preventDefault();
        handleExecute();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [visibleFiles, selectedIndex, activeDirectory, activeExtension, filterText, recursive, barcodeMode]);

  // Apply theme attribute + persist preference
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("profiles-theme", theme);
    } catch {
      /* storage may be unavailable */
    }
  }, [theme]);

  return (
    <div className="flex h-dvh flex-col bg-elevated/30 p-1 font-sans text-ink transition-colors sm:p-1.5">
      {/* Rounded app frame — thin modern border around the whole app. */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-frame-line bg-app shadow-[0_2px_6px_rgb(0_0_0/0.35)] sm:rounded-xl">
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
        onExtensionChange={setActiveExtension}
        filterOptions={config?.filters || []}
        filterText={filterText}
        onFilterTextChange={handleFilterTextChange}
        recursive={recursive}
        onRecursiveChange={handleRecursiveToggle}
        onScan={handleScan}
        scanning={scanning}
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
          totalCount={totalCount}
          onLoadMore={handleLoadMore}
          loadingMore={loadingMore}
          scanning={scanning}
          hasScanned={hasScanned}
          activeDirectory={activeDirectory}
          recursive={recursive}
          onDisableRecursive={handleDisableRecursive}
          onOpenDirectory={handleOpenActiveDirectory}
          onOpenConfig={() => setShowConfigPicker(true)}
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
          sort={sort}
          onSortChange={(next) => {
            setSort(next);
            // Reset the selection anchor; a re-ordered set is authoritative.
            selectedPathRef.current = null;
            setSelectedIndex(0);
            const generation = scanGenerationRef.current;
            setLoadingMore(false);
            void loadScanResults(generation, next);
          }}
        />
      )}

      <ActionBar
        onExecute={handleExecute}
        scanning={scanning}
        scanningDirectory={activeDirectory}
        hasSelection={visibleFiles.length > 0}
        fileCount={visibleFiles.length}
        totalCount={totalCount}
        toastMessage={toastMessage}
        onToastDismiss={dismissToast}
      />

      <StatusBar
        systemInfo={systemInfo}
        fileCount={totalCount}
        theme={theme}
        onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
        onOpenLog={() => setShowLogViewer(true)}
        onOpenConfig={async () => {
          try {
            const res = await openConfigFile();
            showToast(res.message);
          } catch (err: any) {
            showToast(`Failed to open config: ${err.message}`, "error");
          }
        }}
        onLoadConfig={() => setShowConfigPicker(true)}
        onShowShortcuts={() => setShowShortcuts(true)}
        onReloadConfig={handleReloadConfig}
        onExport={handleExport}
        exportDisabled={files.length === 0 || scanning}
        language={language}
        onLanguageChange={setLanguage}
        activeConfigName={config?.config_path ? config.config_path.split(/[\\/]/).pop() || config.config_path : undefined}
      />
      </div>

      {/* Config Picker Modal */}
      <LoadConfigModal
        isOpen={showConfigPicker}
        activeConfigPath={config?.config_path}
        configExists={config?.config_exists}
        onClose={() => setShowConfigPicker(false)}
        onLoaded={handleConfigLoaded}
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
          openLogFile().then((r) => showToast(r.message));
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

      {/* Camera Barcode Scanner Modal */}
      <CameraBarcodeModal
        isOpen={showCameraScanner}
        onClose={() => setShowCameraScanner(false)}
        onDetected={handleCameraDetected}
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
