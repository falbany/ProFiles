import { useState } from "react";
import { Camera, Eye, Play, QrCode, RefreshCw, Search, Timer } from "lucide-react";
import Tooltip from "./Tooltip";
import { EditableCombobox } from "./EditableCombobox";
import { FilterSyntaxHelper } from "./FilterSyntaxHelper";
import { UNLIMITED_SCAN_DEPTH, buildDepthOptions } from "../utils/scanDefaults";

const BASE_OPERATOR_HELP = (
  <span className="flex flex-col gap-1 whitespace-nowrap text-left">
    <span className="font-semibold">Supported operators</span>
    <span>
      <code className="font-mono text-chip-indigo-text">a b</code> — AND (both terms)
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">a OR b</code> — either term
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">-a</code> — NOT (exclude)
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">+a</code> — force include
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">"a b"</code> — exact phrase
    </span>
  </span>
);

// Attribute operators only apply to the filter field (the Ext field is a
// pure substring match), so this section is composed into the filter
// tooltip only (#227).
const FILE_ATTRIBUTE_HELP = (
  <span className="flex flex-col gap-1 whitespace-nowrap text-left">
    <span className="mt-1 font-semibold">File attributes</span>
    <span>
      <code className="font-mono text-chip-indigo-text">size:&gt;10mb</code> — larger than
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">size:1kb..1mb</code> — size range
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">modified:&lt;7d</code> — within the last 7 days
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">modified:&gt;2026-11-01</code> — after a date
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">modified:today</code> — today only
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">created:&gt;2026-11-01</code> — created after a date
    </span>
    <span>
      <code className="font-mono text-chip-indigo-text">created:&lt;7d</code> — created within the last 7 days
    </span>
  </span>
);

const FILTER_OPERATOR_HELP = (
  <>
    {BASE_OPERATOR_HELP}
    {FILE_ATTRIBUTE_HELP}
  </>
);

interface SearchBarProps {
  extensions: string[];
  activeExtension: string;
  onExtensionChange: (ext: string) => void;
  filterOptions?: string[];
  filterText: string;
  onFilterTextChange: (text: string) => void;
  /** Depth currently selected in the UI (1 = selected directory only; #240). */
  depth: number;
  /** Depth pick handler; ∞ arrives as UNLIMITED_SCAN_DEPTH. */
  onDepthChange: (depth: number) => void;
  /** Configured max search depth (pre-clamped by App) — sizes the option list. */
  configDepth: number;
  onScan: () => void;
  scanning: boolean;
  barcodeMode: boolean;
  onBarcodeToggle: () => void;
  onCameraBarcodeClick?: () => void;
  autoRescanActive: boolean;
  onTimerClick: () => void;
  /** Watch mode (#223): whether the server watches the directory for changes. */
  watchActive: boolean;
  /** Watch toggle is unusable (scanning or no active directory). */
  watchDisabled: boolean;
  /** Reported watch cadence, e.g. "2s" — tooltip only; null when unknown. */
  watchLabel: string | null;
  onWatchToggle: () => void;
}

export function SearchBar({
  extensions,
  activeExtension,
  onExtensionChange,
  filterOptions,
  filterText,
  onFilterTextChange,
  depth,
  onDepthChange,
  configDepth,
  onScan,
  scanning,
  barcodeMode,
  onBarcodeToggle,
  onCameraBarcodeClick,
  autoRescanActive,
  onTimerClick,
  watchActive,
  watchDisabled,
  watchLabel,
  onWatchToggle,
}: SearchBarProps) {
  // Whether the filter input itself has focus — drives the live syntax helper.
  const [filterFocused, setFilterFocused] = useState(false);
  // Unfolded combobox lists — tooltips and the syntax helper yield to them (issue #53/#59).
  const [filterListOpen, setFilterListOpen] = useState(false);
  const [extListOpen, setExtListOpen] = useState(false);

  return (
    <div className="flex w-full flex-wrap items-center gap-3 border-b border-line bg-surface-glass p-3 text-xs">
      <Tooltip text={FILTER_OPERATOR_HELP} suppress={filterListOpen}>
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
            onOpenChange={setFilterListOpen}
            placeholder="Filter files: keyword, size:>10mb, modified:<7d, a OR b, -tag..."
            className="w-full"
            inputClassName="pl-9 pr-3"
            optionLabel={(filter) => filter || "(No filter)"}
          />
          {/* Live filter interpretation — visual only, never blocks the input.
              Yields while the preset list is open so it can't cover it (issue #59). */}
          <FilterSyntaxHelper
            query={filterText}
            visible={filterFocused && !filterListOpen && filterText.trim().length > 0}
          />
        </div>
      </Tooltip>

      <Tooltip text={BASE_OPERATOR_HELP} block={false} suppress={extListOpen}>
        <div className="flex shrink-0 items-center gap-1.5">
          <span className="text-ink-muted">Ext:</span>
          <EditableCombobox
            id="extension-combobox"
            ariaLabel="Extension filter"
            value={activeExtension}
            options={extensions}
            onChange={onExtensionChange}
            // Commit on Enter / blur / option pick instead of per keystroke
            // (issue #121); App schedules the deferred rescan on commit.
            commitOn="deferred"
            onOpenChange={setExtListOpen}
            placeholder=".py OR .toml"
            className="w-44"
            inputClassName="font-mono px-2.5"
          />
        </div>
      </Tooltip>

      {/* Scan depth (#240): 1 = selected directory only, N = up to N levels,
          ∞ = unlimited (carried as UNLIMITED_SCAN_DEPTH). Always visible. */}
      <Tooltip
        text="Scan depth — 1: selected directory only; N: up to N levels; ∞: unlimited"
        block={false}
      >
        <label className="flex shrink-0 select-none items-center gap-1.5 text-ink-muted">
          <span>Depth:</span>
          <select
            aria-label="Scan depth"
            value={depth === UNLIMITED_SCAN_DEPTH ? "unlimited" : String(depth)}
            onChange={(e) => {
              const raw = e.target.value;
              onDepthChange(raw === "unlimited" ? UNLIMITED_SCAN_DEPTH : Number(raw));
            }}
            // w-14 fits the widest finite value ("25") plus the native arrow;
            // the ∞ option renders as just "∞" so the closed select stays
            // 2-digit wide. h-[30px] pins the height to the combobox/button
            // height in this bar — WKWebView (pywebview) ignores the padding
            // derived height on native selects and rendered it too small.
            className="h-[30px] w-14 rounded-md border border-line bg-elevated px-2 text-ink-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            {buildDepthOptions(configDepth).map((n) => (
              <option key={n} value={String(n)}>
                {n}
              </option>
            ))}
            <option value="unlimited">∞</option>
          </select>
        </label>
      </Tooltip>

      <Tooltip text="Run the scan with the current criteria (Enter)" block={false}>
        <button
          onClick={onScan}
          disabled={scanning}
          className="btn btn-primary shrink-0 px-3.5 py-1.5 font-semibold shadow-sm"
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
            autoRescanActive ? "border-chip-indigo-border bg-chip-indigo-bg text-chip-indigo-text" : "border-line bg-elevated"
          }`}
        >
          <Timer className={`h-3.5 w-3.5 ${autoRescanActive ? "animate-pulse" : ""}`} />
        </button>
      </Tooltip>

      {/* Watch-mode toggle (#223): rescan when the directory changes — the
          other mode of the same control as the timer, mutually exclusive. */}
      <Tooltip
        text={watchActive ? `Watching · every ${watchLabel ?? "?"}` : "Watch for changes — rescan when the directory changes"}
        block={false}
      >
        <button
          type="button"
          onClick={onWatchToggle}
          disabled={watchDisabled}
          aria-label={watchActive ? "Disable watch mode" : "Enable watch mode"}
          className={`flex shrink-0 items-center justify-center rounded-md border p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors ${
            watchActive ? "border-chip-indigo-border bg-chip-indigo-bg text-chip-indigo-text" : "border-line bg-elevated"
          }`}
        >
          <Eye className={`h-3.5 w-3.5 ${watchActive ? "animate-pulse" : ""}`} />
        </button>
      </Tooltip>

      {/* Barcode scanner mode toggle (moved from the former Row 1) */}
      <Tooltip text="Toggle barcode scanner mode (USB HID). When active, scan a barcode to auto-fill controls and trigger a scan." block={false}>
        <button
          type="button"
          onClick={onBarcodeToggle}
          aria-label={barcodeMode ? "Disable barcode mode" : "Enable barcode mode"}
          className={`flex shrink-0 items-center justify-center rounded-md border p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors ${
            barcodeMode ? "border-chip-indigo-border bg-chip-indigo-bg text-chip-indigo-text" : "border-line bg-elevated"
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
            className="btn btn-secondary shrink-0 p-1.5"
          >
            <Camera className="h-3.5 w-3.5" />
          </button>
        </Tooltip>
      )}
    </div>
  );
}
