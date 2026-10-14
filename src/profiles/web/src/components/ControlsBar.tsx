import { Folder, FolderOpen, Play, RefreshCw, Search } from "lucide-react";
import Tooltip from "./Tooltip";
import { EditableCombobox } from "./EditableCombobox";

const OPERATOR_HELP = (
  <span className="flex flex-col gap-1 whitespace-nowrap text-left">
    <span className="font-semibold">Supported operators</span>
    <span>
      <code className="font-mono text-indigo-300">a b</code> — AND (both terms)
    </span>
    <span>
      <code className="font-mono text-indigo-300">a OR b</code> — either term
    </span>
    <span>
      <code className="font-mono text-indigo-300">-a</code> — NOT (exclude)
    </span>
    <span>
      <code className="font-mono text-indigo-300">+a</code> — force include
    </span>
    <span>
      <code className="font-mono text-indigo-300">"a b"</code> — exact phrase
    </span>
  </span>
);

interface ControlsBarProps {
  directories: string[];
  activeDirectory: string;
  onDirectoryChange: (dir: string) => void;
  extensions: string[];
  activeExtension: string;
  onExtensionChange: (ext: string) => void;
  filterOptions?: string[];
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
  filterOptions = [],
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
      {/* Row 1: Directory selection — spans the full window width */}
      <div className="flex w-full items-center gap-2">
        <label className="flex shrink-0 items-center gap-1.5 font-medium text-ink-secondary">
          <Folder className="h-3.5 w-3.5 text-indigo-400" />
          <span>Directory:</span>
        </label>
        <Tooltip text="Select or type a directory path to scan files from.">
          <EditableCombobox
            id="directory-combobox"
            ariaLabel="Directory"
            value={activeDirectory}
            options={directories}
            onChange={onDirectoryChange}
            placeholder="/path/to/directory"
            className="w-full"
            inputClassName="font-mono"
          />
        </Tooltip>
        {onBrowseDirectory && (
          <Tooltip text="Browse for a folder on this system" block={false}>
            <button
              type="button"
              onClick={onBrowseDirectory}
              aria-label="Browse directory"
              className="rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
            >
              <FolderOpen className="h-3.5 w-3.5" />
            </button>
          </Tooltip>
        )}
      </div>

      {/* Row 2: Search filters and Actions */}
      <div className="flex w-full flex-wrap items-center gap-3">
        <Tooltip text={OPERATOR_HELP}>
          <div className="relative min-w-0 flex-1 basis-64">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-ink-muted" />
            <EditableCombobox
              id="filter-combobox"
              ariaLabel="File filter"
              value={filterText}
              options={filterOptions}
              onChange={onFilterTextChange}
              placeholder="Filter files: keyword, a OR b, -tag, exact phrase..."
              className="w-full"
              inputClassName="rounded-l-md py-1.5 pl-8 pr-3"
              optionLabel={(filter) => filter || "(No filter)"}
            />
          </div>
        </Tooltip>

        <Tooltip text={OPERATOR_HELP} block={false}>
          <div className="flex shrink-0 items-center gap-1.5">
            <span className="text-ink-muted">Ext:</span>
            <EditableCombobox
              id="extension-combobox"
              ariaLabel="Extension filter"
              value={activeExtension}
              options={extensions}
              onChange={onExtensionChange}
              placeholder=".py OR .toml"
              className="w-44"
              inputClassName="font-mono px-2.5"
            />
          </div>
        </Tooltip>

        <Tooltip text="Include subdirectories when scanning" block={false}>
          <label className="flex shrink-0 cursor-pointer select-none items-center gap-1.5 text-ink-secondary">
            <input
              type="checkbox"
              checked={recursive}
              onChange={(e) => onRecursiveChange(e.target.checked)}
              className="rounded border-line text-indigo-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 focus-visible:ring-offset-app"
            />
            <span>Recursive</span>
          </label>
        </Tooltip>

        <Tooltip text="Run the scan with the current criteria (Enter)" block={false}>
          <button
            onClick={onScan}
            disabled={scanning}
            className="flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-600 px-3.5 py-1.5 font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            {scanning ? (
              <RefreshCw className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />
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
