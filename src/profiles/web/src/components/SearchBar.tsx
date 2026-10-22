import { useState } from "react";
import { Camera, Play, QrCode, RefreshCw, Search, Timer } from "lucide-react";
import Tooltip from "./Tooltip";
import { EditableCombobox } from "./EditableCombobox";
import { FilterSyntaxHelper } from "./FilterSyntaxHelper";

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

interface SearchBarProps {
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
  barcodeMode: boolean;
  onBarcodeToggle: () => void;
  onCameraBarcodeClick?: () => void;
  autoRescanActive: boolean;
  onTimerClick: () => void;
}

export function SearchBar({
  extensions,
  activeExtension,
  onExtensionChange,
  filterOptions,
  filterText,
  onFilterTextChange,
  recursive,
  onRecursiveChange,
  onScan,
  scanning,
  barcodeMode,
  onBarcodeToggle,
  onCameraBarcodeClick,
  autoRescanActive,
  onTimerClick,
}: SearchBarProps) {
  // Whether the filter input itself has focus — drives the live syntax helper.
  const [filterFocused, setFilterFocused] = useState(false);

  return (
    <div className="flex w-full flex-wrap items-center gap-3 border-b border-line bg-surface-glass p-3 text-xs">
      <Tooltip text={OPERATOR_HELP}>
        <div
          className="relative min-w-0 flex-1 basis-64"
          onFocusCapture={(event) => {
            if ((event.target as HTMLElement).tagName === "INPUT") setFilterFocused(true);
          }}
          onBlurCapture={(event) => {
            if ((event.target as HTMLElement).tagName === "INPUT") setFilterFocused(false);
          }}
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-ink-secondary" />
          <EditableCombobox
            id="filter-combobox"
            ariaLabel="File filter"
            value={filterText}
            options={filterOptions || []}
            onChange={onFilterTextChange}
            placeholder="Filter files: keyword, a OR b, -tag, exact phrase..."
            className="w-full"
            inputClassName="pl-9 pr-3"
            optionLabel={(filter) => filter || "(No filter)"}
          />
          {/* Live filter interpretation — visual only, never blocks the input. */}
          <FilterSyntaxHelper query={filterText} visible={filterFocused && filterText.trim().length > 0} />
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
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-600 px-3.5 py-1.5 font-semibold text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors"
        >
          {scanning ? (
            <RefreshCw className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" />
          ) : (
            <Play className="h-3.5 w-3.5 fill-current" />
          )}
          <span>{scanning ? "Scanning..." : "Scan"}</span>
        </button>
      </Tooltip>

      {/* Timer / auto-rescan toggle */}
      <Tooltip text={autoRescanActive ? "Auto-rescan is active. Click to configure." : "Configure periodic auto-rescan (hot-folder mode)"} block={false}>
        <button
          type="button"
          onClick={onTimerClick}
          aria-label="Configure timer / auto-rescan"
          className={`flex shrink-0 items-center justify-center rounded-md border p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors ${
            autoRescanActive ? "border-indigo-500 bg-indigo-600/20 text-indigo-400" : "border-line bg-elevated"
          }`}
        >
          <Timer className={`h-3.5 w-3.5 ${autoRescanActive ? "animate-pulse" : ""}`} />
        </button>
      </Tooltip>

      {/* Barcode scanner mode toggle (moved from the former Row 1) */}
      <Tooltip text="Toggle barcode scanner mode (USB HID). When active, scan a barcode to auto-fill controls and trigger a scan." block={false}>
        <button
          type="button"
          onClick={onBarcodeToggle}
          aria-label={barcodeMode ? "Disable barcode mode" : "Enable barcode mode"}
          className={`flex shrink-0 items-center justify-center rounded-md border p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors ${
            barcodeMode ? "border-indigo-500 bg-indigo-600/20 text-indigo-400" : "border-line bg-elevated"
          }`}
        >
          <QrCode className={`h-3.5 w-3.5 ${barcodeMode ? "animate-pulse" : ""}`} />
        </button>
      </Tooltip>

      {/* Camera barcode scanner */}
      {onCameraBarcodeClick && (
        <Tooltip text="Scan barcode or QR code using webcam / camera (Ctrl + Shift + B)" block={false}>
          <button
            type="button"
            onClick={onCameraBarcodeClick}
            aria-label="Scan barcode with camera"
            className="rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors"
          >
            <Camera className="h-3.5 w-3.5" />
          </button>
        </Tooltip>
      )}
    </div>
  );
}
