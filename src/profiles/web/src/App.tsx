import { useEffect, useState } from "react";
import { executeScan, fetchConfig, fetchScanResults, fetchSystemInfo, launchFile } from "./api/client";
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
        if (cfg.active_directory) {
          setActiveDirectory(cfg.active_directory);
        } else if (cfg.directories.length > 0) {
          setActiveDirectory(cfg.directories[0]);
        }
        if (cfg.extensions.length > 0) {
          setActiveExtension(cfg.extensions[0]);
        }
      } catch (err) {
        console.error("Initialization error:", err);
      }
    }
    init();
  }, []);

  // Run scan
  const handleScan = async () => {
    if (!activeDirectory) return;
    setScanning(true);
    try {
      await executeScan({
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
        onDirectoryChange={setActiveDirectory}
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
