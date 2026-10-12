import { useEffect, useState } from "react";
import { executeScan, fetchConfig, fetchScanResults, fetchSystemInfo, launchFile, selectDirectory } from "./api/client";
import type { AppConfigData, ScannedFileItem, SystemInfo } from "./api/types";
import { ActionBar } from "./components/ActionBar";
import { ControlsBar } from "./components/ControlsBar";
import { FileListTable } from "./components/FileListTable";
import { HeaderBar } from "./components/HeaderBar";
import { StatusBar } from "./components/StatusBar";

export default function App() {
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

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) {
        if (e.key === "Enter") {
          handleScan();
        }
        return;
      }
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

  return (
    <div className="flex h-screen flex-col bg-slate-950 font-sans text-slate-100">
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
      />
    </div>
  );
}
