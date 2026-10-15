import { useEffect, useRef, useState } from "react";
import {
  computeHash,
  executeScan,
  fetchConfig,
  fetchScanResults,
  fetchSystemInfo,
  launchFile,
  launchWithArgs,
  openConfigFile,
  openFolder,
  openLogFile,
  openTerminal,
  revealFile,
  selectDirectory,
} from "./api/client";
import type { AppConfigData, ScanSort, ScannedFileItem, SystemInfo } from "./api/types";
import { ActionBar } from "./components/ActionBar";
import { ContextMenu, type ContextMenuPosition } from "./components/ContextMenu";
import { ControlsBar } from "./components/ControlsBar";
import { DirectoryPickerModal } from "./components/DirectoryPickerModal";
import { FileListTable, SCAN_PAGE_SIZE } from "./components/FileListTable";
import { HeaderBar } from "./components/HeaderBar";
import { LogViewerModal } from "./components/LogViewerModal";
import { ShortcutsModal } from "./components/ShortcutsModal";
import { LoadConfigModal } from "./components/LoadConfigModal";
import { StatusBar } from "./components/StatusBar";

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
  /** Column the list is ordered by, or `null` for scan order. */
  const [sort, setSort] = useState<ScanSort | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [scanning, setScanning] = useState<boolean>(false);
  const scanGenerationRef = useRef(0);

  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [showShortcuts, setShowShortcuts] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string>("");
  const [reloading, setReloading] = useState<boolean>(false);
  const [language, setLanguage] = useState<"en" | "fr">("en");
  const [showDirPicker, setShowDirPicker] = useState<boolean>(false);
  const [showConfigPicker, setShowConfigPicker] = useState<boolean>(false);
  const [showLogViewer, setShowLogViewer] = useState<boolean>(false);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(""), 3500);
  };

  const beginScan = () => {
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
    await executeScan(params);
    if (!isCurrentScan(generation) || !(await loadScanResults(generation))) return false;
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
      /* paging failure is non-fatal; user can keep scrolling to retry */
    } finally {
      if (isCurrentScan(generation)) setLoadingMore(false);
    }
  };

  const loadConfig = async () => {
    try {
      const cfg = await fetchConfig();
      setConfig(cfg);
      if (!activeDirectory && cfg.active_directory) {
        setActiveDirectory(cfg.active_directory);
      }
      if (!activeExtension && cfg.extensions.length > 0) {
        setActiveExtension(cfg.extensions[0]);
      }
      if (cfg.recursive_search !== undefined) {
        setRecursive(cfg.recursive_search);
      }
      if (!filterText && cfg.filters.length > 0) {
        setFilterText(cfg.filters[0]);
      }
      return cfg;
    } catch (err: any) {
      showToast(`Failed to load configuration: ${err.message}`);
      return null;
    }
  };

  const handleReloadConfig = async () => {
    if (reloading) return;
    setReloading(true);
    showToast("Reloading configuration...");
    try {
      const cfg = await loadConfig();
      if (cfg) {
        showToast("Configuration reloaded.");
        await handleScan();
      }
    } finally {
      setReloading(false);
    }
  };

  const handleConfigLoaded = async (cfg: AppConfigData) => {
    const scanGeneration = beginScan();
    setConfig(cfg);
    const targetDirectory = cfg.active_directory || activeDirectory || (cfg.directories[0] ?? "");
    const nextExtension = cfg.extensions.includes(activeExtension)
      ? activeExtension
      : (cfg.extensions[0] ?? "");
    const nextFilter = cfg.filters.includes(filterText) ? filterText : (cfg.filters[0] ?? "");
    if (targetDirectory) {
      setActiveDirectory(targetDirectory);
    }
    setActiveExtension(nextExtension);
    setFilterText(nextFilter);
    setRecursive(cfg.recursive_search);

    showToast(cfg.config_exists ? `Loaded config: ${cfg.config_path}` : "Starter configuration created.");
    if (targetDirectory) {
      try {
        await runScan(scanGeneration, {
          directory: targetDirectory,
          extension: nextExtension,
          filter_text: nextFilter,
          recursive: cfg.recursive_search,
        });
      } catch (err: any) {
        showToast(`Scan failed after config load: ${err.message}`);
      } finally {
        finishScan(scanGeneration);
      }
    } else {
      finishScan(scanGeneration);
    }
  };

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
      if (isCurrentScan(scanGeneration)) showToast(`Scan failed: ${err.message}`);
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
      } catch (scanErr) {
        if (isCurrentScan(scanGeneration)) console.error("Initial scan error:", scanErr);
      }
    }
  };

  // Initial load
  useEffect(() => {
    async function init() {
      const scanGeneration = ++scanGenerationRef.current;
      try {
        const sys = await fetchSystemInfo();
        setSystemInfo(sys);
        const cfg = await fetchConfig();
        await initializeFromConfig(cfg, scanGeneration);
      } catch (err) {
        console.error("Initialization error:", err);
      }
    }
    init();
  }, []);

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
    } catch (err) {
      if (isCurrentScan(scanGeneration)) console.error("Directory change error:", err);
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

  // Launch file
  const handleLaunch = async (file: ScannedFileItem) => {
    try {
      await launchFile({
        directory: activeDirectory,
        filename: file.rel_path,
        release: config?.release,
      });
    } catch (err) {
      console.error("Launch error:", err);
    }
  };

  const handleExecute = () => {
    if (files.length > 0 && files[selectedIndex]) {
      handleLaunch(files[selectedIndex]);
    }
  };

  // Context menu actions
  const handleLaunchWithArgs = async (file: ScannedFileItem, args: string) => {
    try {
      const res = await launchWithArgs(file.path, args);
      showToast(res.message || "File launched with arguments.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`);
    }
  };

  const handleReveal = async (file: ScannedFileItem) => {
    try {
      await revealFile(file.path);
      showToast("Revealed in file manager.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`);
    }
  };

  const handleOpenFolder = async (file: ScannedFileItem) => {
    try {
      await openFolder(file.path);
      showToast("Folder opened in file manager.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`);
    }
  };

  const handleOpenTerminal = async (file: ScannedFileItem) => {
    try {
      const res = await openTerminal(file.path);
      showToast(res.message || "Terminal opened.");
    } catch (err: any) {
      showToast(`Error: ${err.message}`);
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
      showToast(`Hash computation failed: ${err.message}`);
    }
  };

  const handleCopyUri = async (file: ScannedFileItem) => {
    try {
      const uri = new URL("file:///").href + file.path.replace(/\\/g, "/");
      navigator.clipboard.writeText(uri);
      showToast("File URI copied to clipboard.");
    } catch (err: any) {
      showToast(`URI copy failed: ${err.message}`);
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
      showToast(`Verification failed: ${err.message}`);
    }
  };

  const handleProperties = async (file: ScannedFileItem) => {
    try {
      showToast("Fetching properties...");
      const res = await fetch(`/api/actions/metadata`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: file.path }),
      });
      if (!res.ok) throw new Error("Failed to fetch metadata");
      const meta = await res.json();
      const sizeKb = meta.size_bytes / 1024;
      const info = `File: ${meta.name}\nPath: ${meta.path}\n\nSize: ${meta.size_bytes.toLocaleString()} bytes (${sizeKb.toFixed(1)} KB)\nModified: ${meta.modified}\nCreated: ${meta.created}`;
      alert(info);
    } catch (err: any) {
      showToast(`Properties failed: ${err.message}`);
    }
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
      showToast(`Delete failed: ${err.message}`);
    }
  };

  const handleRefreshList = () => {
    handleScan();
  };

  // Keyboard navigation & global shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Allow Esc to close context menu or modals
      if (e.key === "Escape") {
        setContextMenuPos(null);
        setShowShortcuts(false);
        setShowLogViewer(false);
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
        const file = files[selectedIndex];
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

      // ? or Ctrl + /: Show shortcuts
      if (e.key === "?" || (e.ctrlKey && e.key === "/")) {
        e.preventDefault();
        setShowShortcuts((prev) => !prev);
        return;
      }

      // Table navigation
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.min(prev + 1, Math.max(0, files.length - 1)));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        handleExecute();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [files, selectedIndex, activeDirectory, activeExtension, filterText, recursive]);

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
    <div className="flex h-screen flex-col bg-app font-sans text-ink transition-colors">
      <HeaderBar
        title={config?.title || ""}
        release={config?.release || ""}
        systemInfo={systemInfo}
      />

      <ControlsBar
        directories={config?.directories || []}
        activeDirectory={activeDirectory}
        onDirectoryChange={handleDirectoryChange}
        extensions={config?.extensions || []}
        activeExtension={activeExtension}
        onExtensionChange={setActiveExtension}
        filterOptions={config?.filters || []}
        filterText={filterText}
        onFilterTextChange={setFilterText}
        recursive={recursive}
        onRecursiveChange={setRecursive}
        onScan={handleScan}
        scanning={scanning}
        onBrowseDirectory={handleBrowseDirectory}
      />

      <FileListTable
        files={files}
        totalCount={totalCount}
        onLoadMore={handleLoadMore}
        loadingMore={loadingMore}
        scanning={scanning}
        hasScanned={hasScanned}
        filterText={filterText}
        onClearFilter={handleClearFilter}
        columnHeaders={config?.column_headers || []}
        columnNames={config?.column_names || []}
        selectedIndex={selectedIndex}
        onSelectIndex={setSelectedIndex}
        onLaunch={handleLaunch}
        onContextMenu={(e, file, idx) => {
          e.preventDefault();
          setSelectedIndex(idx);
          setContextMenuPos({ x: e.clientX, y: e.clientY, file });
        }}
        rowColors={config?.row_colors || []}
        sort={sort}
        onSortChange={(next) => {
          setSort(next);
          setSelectedIndex(0);
          const generation = scanGenerationRef.current;
          setLoadingMore(false);
          void loadScanResults(generation, next);
        }}
      />

      <ActionBar
        onExecute={handleExecute}
        scanning={scanning}
        hasSelection={files.length > 0}
      />

      <StatusBar
        systemInfo={systemInfo}
        activeDirectory={activeDirectory}
        fileCount={totalCount}
        theme={theme}
        onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
        onOpenLog={() => setShowLogViewer(true)}
        onOpenConfig={async () => {
          try {
            const res = await openConfigFile();
            showToast(res.message);
          } catch (err: any) {
            showToast(`Failed to open config: ${err.message}`);
          }
        }}
        onLoadConfig={() => setShowConfigPicker(true)}
        onShowShortcuts={() => setShowShortcuts(true)}
        onReloadConfig={handleReloadConfig}
        language={language}
        onLanguageChange={setLanguage}
        activeConfigName={config?.config_path ? config.config_path.split(/[\\/]/).pop() || config.config_path : undefined}
      />

      {/* Config Picker Modal */}
      <LoadConfigModal
        isOpen={showConfigPicker}
        activeConfigPath={config?.config_path}
        configExists={config?.config_exists}
        onClose={() => setShowConfigPicker(false)}
        onLoaded={handleConfigLoaded}
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
        onFilterFolder={handleFilterFolder}
        onFilterExtension={handleFilterExtension}
        onCopyPath={handleCopyPath}
        onCopyFilename={handleCopyFilename}
        onCopyUri={handleCopyUri}
        onComputeHash={handleComputeHash}
        onVerifyHash={handleVerifyHash}
        onProperties={handleProperties}
        onClearFile={handleClearFile}
        onRefreshList={handleRefreshList}
      />

      {/* Shortcuts Modal */}
      <ShortcutsModal isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />

      {/* Log Viewer Modal */}
      <LogViewerModal
        isOpen={showLogViewer}
        onClose={() => setShowLogViewer(false)}
        onOpenExternally={() => {
          openLogFile().then((r) => showToast(r.message));
        }}
      />

      {/* Toast Notification */}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className={toastMessage
          ? "fixed bottom-12 right-6 z-50 rounded-lg border border-line bg-surface-glass px-4 py-2 text-xs font-medium text-ink shadow-xl backdrop-blur-md"
          : "sr-only"}
      >
        {toastMessage}
      </div>
    </div>
  );
}
