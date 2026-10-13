import { Folder, FolderOpen, Play, RefreshCw, Search } from "lucide-react";
import Tooltip from "./Tooltip";

interface ControlsBarProps {
  directories: string[];
  activeDirectory: string;
  onDirectoryChange: (dir: string) => void;
  extensions: string[];
  activeExtension: string;
  onExtensionChange: (ext: string) => void;
  filterText: string;
  onFilterTextChange: (text: string) => void;
  recursive: boolean;
  onRecursiveChange: (val: boolean) => void;
  onScan: () => void;
  scanning: boolean;
  onBrowseDirectory?: () => void;
}

export function ControlsBar({
  directories,
  activeDirectory,
  onDirectoryChange,
  extensions,
  activeExtension,
  onExtensionChange,
  filterText,
  onFilterTextChange,
  recursive,
  onRecursiveChange,
  onScan,
  scanning,
  onBrowseDirectory,
}: ControlsBarProps) {
  return (
    <div className="flex flex-col gap-2.5 border-b border-line bg-surface-glass p-3 text-xs">
      {/* Row 1: Directory selection */}
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-1.5 font-medium text-ink-secondary">
          <Folder className="h-3.5 w-3.5 text-indigo-400" />
          <span>Directory:</span>
        </label>
        <Tooltip text="Select or type a directory path to scan files from.">
          <input
            type="text"
            list="directories-list"
            value={activeDirectory}
            placeholder="/path/to/directory"
            onChange={(e) => onDirectoryChange(e.target.value)}
            className="flex-1 rounded-md border border-line bg-elevated px-3 py-1.5 font-mono text-ink outline-none focus:border-indigo-500"
          />
        </Tooltip>
        <datalist id="directories-list">
          {directories.map((dir) => (
            <option key={dir} value={dir} />
          ))}
        </datalist>
        {onBrowseDirectory && (
          <Tooltip text="Browse for a folder on this system">
            <button
              type="button"
              onClick={onBrowseDirectory}
              aria-label="Browse directory"
              className="rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-white"
            >
              <FolderOpen className="h-3.5 w-3.5" />
            </button>
          </Tooltip>
        )}
      </div>

      {/* Row 2: Search filters and Actions */}
      <div className="flex items-center gap-3">
        <Tooltip text="Filter files by name, tags, or operators (AND / OR / NOT, field:value).">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-ink-muted" />
            <input
              type="text"
              placeholder="Filter files (keyword, tags, operators)..."
              value={filterText}
              onChange={(e) => onFilterTextChange(e.target.value)}
              className="w-full rounded-md border border-line bg-elevated py-1.5 pl-8 pr-3 text-ink outline-none focus:border-indigo-500"
            />
          </div>
        </Tooltip>

        <Tooltip text="File extension filter, e.g. .mttl, .py. Leave empty for all.">
          <div className="flex items-center gap-1.5">
            <span className="text-ink-muted">Ext:</span>
            <div className="relative">
              <input
                type="text"
                list="extensions-list"
                value={activeExtension}
                onChange={(e) => onExtensionChange(e.target.value)}
                placeholder="e.g. .mttl, .py"
                className="w-28 rounded-md border border-line bg-elevated px-2.5 py-1.5 font-mono text-ink outline-none focus:border-indigo-500"
              />
              <datalist id="extensions-list">
                {extensions.map((ext) => (
                  <option key={ext} value={ext} />
                ))}
              </datalist>
            </div>
          </div>
        </Tooltip>

        <Tooltip text="Include subdirectories when scanning">
          <label className="flex cursor-pointer select-none items-center gap-1.5 text-ink-secondary">
            <input
              type="checkbox"
              checked={recursive}
              onChange={(e) => onRecursiveChange(e.target.checked)}
              className="rounded border-line text-indigo-600 focus:ring-0"
            />
            <span>Recursive</span>
          </label>
        </Tooltip>

        <Tooltip text="Run the scan with the current criteria (Enter)">
          <button
            onClick={onScan}
            disabled={scanning}
            className="flex items-center gap-1.5 rounded-md bg-indigo-600 px-3.5 py-1.5 font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
          >
            {scanning ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5 fill-current" />
            )}
            <span>{scanning ? "Scanning..." : "Scan"}</span>
          </button>
        </Tooltip>
      </div>
    </div>
  );
}
