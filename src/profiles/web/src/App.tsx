import { useEffect, useState } from "react";
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
import type { AppConfigData, ScannedFileItem, SystemInfo } from "./api/types";
import { ActionBar } from "./components/ActionBar";
import { ContextMenu, type ContextMenuPosition } from "./components/ContextMenu";
import { ControlsBar } from "./components/ControlsBar";
import { FileListTable } from "./components/FileListTable";
import { HeaderBar } from "./components/HeaderBar";
import { ShortcutsModal } from "./components/ShortcutsModal";
import { StatusBar } from "./components/StatusBar";

export default function App() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);
  const [config, setConfig] = useState<AppConfigData | null>(null);

  const [activeDirectory, setActiveDirectory] = useState<string>("");
  const [activeExtension, setActiveExtension] = useState<string>("");
  const [filterText, setFilterText] = useState<string>("");
  const [recursive, setRecursive] = useState<boolean>(true);
  const [closeOnLaunch, setCloseOnLaunch] = useState<boolean>(false);

  const [files, setFiles] = useState<ScannedFileItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState<number>(0);
  const [scanning, setScanning] = useState<boolean>(false);

  const [contextMenuPos, setContextMenuPos] = useState<ContextMenuPosition | null>(null);
  const [showShortcuts, setShowShortcuts] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string>("");

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(""), 3500);
  };

  // Initial load
  useEffect(() => {
    async function init() {
      try {
        const sys = await fetchSystemInfo();
        setSystemInfo(sys);
        const cfg = await fetchConfig();
        setConfig(cfg);
        const initialDir = cfg.active_directory || (cfg.directories.length > 0 ? cfg.directories[0] : "");
        const initialExt = cfg.extensions.length > 0 ? cfg.extensions[0] : "";
        if (initialDir) setActiveDirectory(initialDir);
        if (initialExt) setActiveExtension(initialExt);

        if (initialDir) {
          try {
            await executeScan({
              directory: initialDir,
              extension: initialExt,
              filter_text: "",
              recursive: true,
            });
            const scanRes = await fetchScanResults();
            setFiles(scanRes.items);
          } catch (scanErr) {
            console.error("Initial scan error:", scanErr);
          }
        }
      } catch (err) {
        console.error("Initialization error:", err);
      }
    }
    init();
  }, []);

  // Directory change handler
  const handleDirectoryChange = async (newDir: string) => {
    setActiveDirectory(newDir);
    try {
      await selectDirectory(newDir);
      setScanning(true);
      await executeScan({
        directory: newDir,
        extension: activeExtension,
        filter_text: filterText,
        recursive,
      });
      const res = await fetchScanResults();
      setFiles(res.items);
      setSelectedIndex(0);
    } catch (err) {
      console.error("Directory change error:", err);
    } finally {
      setScanning(false);
    }
  };

  // Run scan
  const handleScan = async () => {
    if (!activeDirectory) return;
    setScanning(true);
    try {
      await executeScan({
        directory: activeDirectory,
        extension: activeExtension,
        filter_text: filterText,
        recursive,
      });
      const res = await fetchScanResults();
      setFiles(res.items);
      setSelectedIndex(0);
    } catch (err) {
      console.error("Scan error:", err);
    } finally {
      setScanning(false);
    }
  };

  // Launch file
  const handleLaunch = async (file: ScannedFileItem) => {
    try {
      await launchFile({
        directory: activeDirectory,
        filename: file.filename,
        release: config?.release,
      });
      if (closeOnLaunch) {
        window.close();
      }
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
    executeScan({
      directory: activeDirectory,
      extension: activeExtension,
      filter_text: folder,
      recursive,
    }).then(() => fetchScanResults().then((res) => { setFiles(res.items); setSelectedIndex(0); }));
  };

  const handleFilterExtension = (ext: string) => {
    setActiveExtension(ext);
    executeScan({
      directory: activeDirectory,
      extension: ext,
      filter_text: filterText,
      recursive,
    }).then(() => fetchScanResults().then((res) => { setFiles(res.items); setSelectedIndex(0); }));
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

  // Keyboard navigation & global shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Allow Esc to close context menu or modals
      if (e.key === "Escape") {
        setContextMenuPos(null);
        setShowShortcuts(false);
        return;
      }

      // If typing in input / select, handle Enter for scan
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) {
        if (e.key === "Enter") {
          handleScan();
        }
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
        fetchConfig().then(setConfig);
        handleScan();
        return;
      }

      // Ctrl + D: Focus directory
      if (e.ctrlKey && e.key.toLowerCase() === "d") {
        e.preventDefault();
        const dirSelect = document.querySelector("select") as HTMLSelectElement | null;
        dirSelect?.focus();
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

      // Ctrl + Shift + L: Open log
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "l") {
        e.preventDefault();
        openLogFile().then((r) => showToast(r.message));
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

  const themeClasses = theme === "dark" ? "bg-slate-950 text-slate-100" : "bg-slate-100 text-slate-900";

  return (
    <div className={`flex h-screen flex-col font-sans ${themeClasses}`}>
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
        filterText={filterText}
        onFilterTextChange={setFilterText}
        recursive={recursive}
        onRecursiveChange={setRecursive}
        onScan={handleScan}
        scanning={scanning}
      />

      <FileListTable
        files={files}
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
      />

      <ActionBar
        onExecute={handleExecute}
        closeOnLaunch={closeOnLaunch}
        onCloseOnLaunchChange={setCloseOnLaunch}
        scanning={scanning}
        hasSelection={files.length > 0}
      />

      <StatusBar
        systemInfo={systemInfo}
        activeDirectory={activeDirectory}
        fileCount={files.length}
        theme={theme}
        onToggleTheme={() => setTheme((prev) => (prev === "dark" ? "light" : "dark"))}
        onOpenLog={async () => {
          try {
            const res = await openLogFile();
            showToast(res.message);
          } catch (err: any) {
            showToast(`Failed to open log: ${err.message}`);
          }
        }}
        onOpenConfig={async () => {
          try {
            const res = await openConfigFile();
            showToast(res.message);
          } catch (err: any) {
            showToast(`Failed to open config: ${err.message}`);
          }
        }}
        onShowShortcuts={() => setShowShortcuts(true)}
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
        onComputeHash={handleComputeHash}
      />

      {/* Shortcuts Modal */}
      <ShortcutsModal isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-12 right-6 z-50 rounded-lg border border-slate-700 bg-slate-900/95 px-4 py-2 text-xs font-medium text-slate-200 shadow-xl backdrop-blur-md">
          {toastMessage}
        </div>
      )}
    </div>
  );
}
