import { Folder, Play, RefreshCw, Search } from "lucide-react";

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
}: ControlsBarProps) {
  return (
    <div className="flex flex-col gap-2.5 border-b border-slate-800 bg-slate-900/60 p-3 text-xs">
      {/* Row 1: Directory selection */}
      <div className="flex items-center gap-2">
        <label className="flex items-center gap-1.5 font-medium text-slate-300">
          <Folder className="h-3.5 w-3.5 text-indigo-400" />
          <span>Directory:</span>
        </label>
        <select
          value={activeDirectory}
          onChange={(e) => onDirectoryChange(e.target.value)}
          className="flex-1 rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 font-mono text-slate-200 outline-none focus:border-indigo-500"
        >
          {directories.map((dir) => (
            <option key={dir} value={dir}>
              {dir}
            </option>
          ))}
        </select>
      </div>

      {/* Row 2: Search filters and Actions */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            placeholder="Filter files (keyword, tags)..."
            value={filterText}
            onChange={(e) => onFilterTextChange(e.target.value)}
            className="w-full rounded-md border border-slate-700 bg-slate-800 py-1.5 pl-8 pr-3 text-slate-200 outline-none focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-slate-400">Ext:</span>
          <div className="relative">
            <input
              type="text"
              list="extensions-list"
              value={activeExtension}
              onChange={(e) => onExtensionChange(e.target.value)}
              placeholder="e.g. .mttl, .py"
              className="w-28 rounded-md border border-slate-700 bg-slate-800 px-2.5 py-1.5 font-mono text-slate-200 outline-none focus:border-indigo-500"
            />
            <datalist id="extensions-list">
              {extensions.map((ext) => (
                <option key={ext} value={ext} />
              ))}
            </datalist>
          </div>
        </div>

        <label className="flex cursor-pointer select-none items-center gap-1.5 text-slate-300">
          <input
            type="checkbox"
            checked={recursive}
            onChange={(e) => onRecursiveChange(e.target.checked)}
            className="rounded border-slate-700 text-indigo-600 focus:ring-0"
          />
          <span>Recursive</span>
        </label>

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
      </div>
    </div>
  );
}
