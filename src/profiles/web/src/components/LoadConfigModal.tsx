import { useEffect, useState } from "react";
import { Check, ChevronRight, FileCog, FileText, Folder, FolderOpen, Home, X } from "lucide-react";

import { browseForConfigFiles, createConfigFile, loadConfigFile } from "../api/client";
import type { AppConfigData, BrowseResult } from "../api/types";

export interface LoadConfigModalProps {
  isOpen: boolean;
  activeConfigPath?: string;
  configExists?: boolean;
  onClose: () => void;
  onLoaded: (config: AppConfigData) => void;
}

export function LoadConfigModal({
  isOpen,
  activeConfigPath,
  configExists = true,
  onClose,
  onLoaded,
}: LoadConfigModalProps) {
  const [browseData, setBrowseData] = useState<BrowseResult | null>(null);
  const [pathInput, setPathInput] = useState<string>("");
  const [selectedConfig, setSelectedConfig] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isCreateMode = configExists === false;

  useEffect(() => {
    if (!isOpen) return;

    setError(null);
    const initialPath = activeConfigPath ? activeConfigPath.split(/[\\/]/).slice(0, -1).join("\\") || activeConfigPath : "";
    browse(initialPath || "");
  }, [isOpen, activeConfigPath]);

  const browse = async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await browseForConfigFiles(path);
      setBrowseData(data);
      setPathInput(data.current_path);
      if (activeConfigPath && data.items.some((item) => item.path === activeConfigPath)) {
        setSelectedConfig(activeConfigPath);
      } else {
        setSelectedConfig(null);
      }
    } catch (err: any) {
      setError(err.message || "Navigation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleLoadSelected = async () => {
    const target = selectedConfig || (browseData?.items.find((item) => item.is_config)?.path ?? null);
    if (!target) {
      setError("Select a configuration file to load.");
      return;
    }

    try {
      setLoading(true);
      const config = await loadConfigFile(target);
      onLoaded(config);
      onClose();
    } catch (err: any) {
      setError(err.message || "Unable to load configuration");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    const targetDirectory = (pathInput || browseData?.current_path || "").trim();
    if (!targetDirectory) {
      setError("Choose a directory before creating a configuration.");
      return;
    }

    try {
      setLoading(true);
      const config = await createConfigFile(targetDirectory);
      onLoaded(config);
      onClose();
    } catch (err: any) {
      setError(err.message || "Unable to create configuration");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-xl border border-line bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div className="flex items-center gap-2">
            <FileCog className="h-4 w-4 text-indigo-400" />
            <h2 className="text-sm font-semibold text-ink">
              {isCreateMode ? "Create configuration" : "Load configuration"}
            </h2>
          </div>
          <button
            onClick={onClose}
            title="Close"
            className="rounded p-1 text-ink-muted hover:bg-elevated hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {isCreateMode && (
          <div className="border-b border-line bg-indigo-600/5 px-4 py-3 text-xs text-ink-secondary">
            No configuration file was found. Create one here?
          </div>
        )}

        <div className="flex gap-2 border-b border-line px-4 py-2.5">
          <input
            type="text"
            value={pathInput}
            onChange={(e) => setPathInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") browse(pathInput.trim());
            }}
            placeholder="/path/to/directory"
            className="flex-1 rounded-md border border-line bg-elevated px-3 py-1.5 font-mono text-xs text-ink outline-none focus:border-indigo-500"
          />
          <button
            onClick={() => browse(pathInput.trim())}
            className="rounded-md border border-line bg-elevated px-2.5 text-xs text-ink-secondary hover:text-white"
          >
            Go
          </button>
          <button
            onClick={() => browse("")}
            title="Home directory"
            className="rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:text-white"
          >
            <Home className="h-3.5 w-3.5" />
          </button>
          {browseData?.parent_path && (
            <button
              onClick={() => browse(browseData.parent_path!)}
              title="Parent directory"
              className="rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:text-white"
            >
              <ChevronRight className="h-3.5 w-3.5 rotate-180" />
            </button>
          )}
        </div>

        <div className="max-h-80 overflow-y-auto px-2 py-2">
          {loading ? (
            <div className="flex h-32 items-center justify-center text-xs text-ink-muted">Loading…</div>
          ) : error ? (
            <div className="px-4 py-8 text-center text-xs text-rose-400">{error}</div>
          ) : (
            <ul className="space-y-1">
              {browseData?.items.map((item) => {
                if (item.is_dir) {
                  return (
                    <li key={item.path}>
                      <button
                        onClick={() => browse(item.path)}
                        onDoubleClick={() => browse(item.path)}
                        className="flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left text-xs text-ink-secondary hover:bg-elevated"
                      >
                        <span className="flex items-center gap-2">
                          <Folder className="h-3.5 w-3.5 text-indigo-400" />
                          {item.name}
                        </span>
                      </button>
                    </li>
                  );
                }

                const isSelected = selectedConfig === item.path;
                return (
                  <li key={item.path}>
                    <button
                      onClick={() => setSelectedConfig(item.path)}
                      className={`flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left text-xs transition-colors ${
                        isSelected ? "bg-indigo-600/15 text-indigo-100" : "text-ink-secondary hover:bg-elevated"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <FileText className="h-3.5 w-3.5 text-amber-400" />
                        {item.name}
                      </span>
                      {item.is_config && <FileCog className="h-3.5 w-3.5 text-indigo-400" />}
                      {isSelected && <Check className="h-3.5 w-3.5 text-indigo-400" />}
                    </button>
                  </li>
                );
              })}

              {browseData?.items.length === 0 && (
                <li className="px-4 py-6 text-center text-xs text-ink-faint">No matching config files here</li>
              )}
            </ul>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-line px-4 py-3">
          <div className="flex items-center gap-1.5 text-[11px] text-ink-faint">
            <FolderOpen className="h-3 w-3" />
            <span className="max-w-[260px] truncate font-mono">{pathInput || browseData?.current_path || ""}</span>
          </div>

          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-md px-3 py-1.5 text-xs text-ink-muted hover:text-ink"
            >
              Cancel
            </button>
            {isCreateMode ? (
              <button
                onClick={handleCreate}
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500"
              >
                Create .profiles
              </button>
            ) : (
              <button
                onClick={handleLoadSelected}
                disabled={!selectedConfig}
                className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                Load
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
