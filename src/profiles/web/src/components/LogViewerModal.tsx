import Tooltip from "./Tooltip";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import {
  AlertTriangle,
  ArrowDown,
  Bug,
  Copy,
  ExternalLink,
  FileText,
  Info,
  RefreshCw,
  Search,
  X,
  XCircle,
} from "lucide-react";

import { fetchLogEntries } from "../api/client";
import type { LogEntry, LogLevel } from "../api/types";

/** Poll cadence for the live tail, in milliseconds. */
const POLL_INTERVAL_MS = 2000;
/** Entries requested per poll — the newest window of the log tail. */
const PAGE_LIMIT = 500;

const LEVEL_FILTERS: Array<{ value: LogLevel | null; label: string }> = [
  { value: null, label: "ALL" },
  { value: "DEBUG", label: "DEBUG" },
  { value: "INFO", label: "INFO" },
  { value: "WARNING", label: "WARNING" },
  { value: "ERROR", label: "ERROR" },
  { value: "CRITICAL", label: "CRITICAL" },
];

/** Level → icon + text colour. Accessible pairs on the dark surface. */
const LEVEL_STYLE: Record<LogEntry["level"], { icon: typeof Info; className: string }> = {
  DEBUG: { icon: Bug, className: "text-chip-sky-text" },
  INFO: { icon: Info, className: "text-status-success-text" },
  WARNING: { icon: AlertTriangle, className: "text-status-warning-text" },
  ERROR: { icon: XCircle, className: "text-status-danger-text" },
  CRITICAL: { icon: XCircle, className: "text-status-danger-text" },
  UNKNOWN: { icon: FileText, className: "text-ink-faint" },
};

export interface LogViewerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenExternally?: () => void;
}

export function LogViewerModal({ isOpen, onClose, onOpenExternally }: LogViewerModalProps) {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [logPath, setLogPath] = useState<string>("profiles.log");
  const [sizeBytes, setSizeBytes] = useState<number>(0);
  const [level, setLevel] = useState<LogLevel | null>(null);
  const [search, setSearch] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [live, setLive] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  /** When true, the newest entry stays pinned to the bottom on refresh. */
  const [followTail, setFollowTail] = useState<boolean>(true);

  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  /** Kept in a ref so the poll effect can re-read it without re-subscribing. */
  const liveRef = useRef(live);
  const filterRef = useRef<{ level: LogLevel | null; search: string }>({ level, search });

  liveRef.current = live;
  filterRef.current = { level, search };

  const load = useCallback(async () => {
    const { level: activeLevel, search: activeSearch } = filterRef.current;
    setLoading(true);
    try {
      const data = await fetchLogEntries({
        limit: PAGE_LIMIT,
        level: activeLevel,
        search: activeSearch,
      });
      setEntries(data.entries);
      setLogPath(data.path);
      setSizeBytes(data.size_bytes);
      setError(null);
    } catch (err) {
      setError((err as Error)?.message || "Failed to read the log file");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch whenever the dialog opens.
  useEffect(() => {
    if (!isOpen) return;
    void load();
  }, [isOpen, load]);

  // Live tail — refetch on an interval while enabled.
  useEffect(() => {
    if (!isOpen || !live) return;
    const timer = window.setInterval(() => {
      void load();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [isOpen, live, load]);

  // Debounce text filter input instead of firing a request per keystroke.
  useEffect(() => {
    if (!isOpen) return;
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [isOpen, level, search, load]);

  // Keep the newest entry in view while following the tail.
  useEffect(() => {
    if (!followTail) return;
    const scroller = scrollRef.current;
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [entries, followTail]);

  // Restrict focus to the dialog and return it to the opener on close.
  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = requestAnimationFrame(() => closeButtonRef.current?.focus());
    return () => {
      cancelAnimationFrame(frame);
      previous?.focus();
    };
  }, [isOpen]);

  const handleDialogKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;

    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable?.length) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  /** Tracks manual scrolling so we stop following once the user scrolls up. */
  const handleScroll = () => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    const atBottom = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 24;
    setFollowTail(atBottom);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(entries.map((entry) => entry.raw).join("\n"));
    } catch {
      /* clipboard unavailable — the external-open fallback still applies */
    }
  };

  const levelCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const entry of entries) {
      counts.set(entry.level, (counts.get(entry.level) ?? 0) + 1);
    }
    return counts;
  }, [entries]);

  if (!isOpen) return null;

  return (
    <div
      animate-overlay-in className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-3 backdrop-blur-sm sm:p-6"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="log-viewer-title"
        onKeyDown={handleDialogKeyDown}
        animate-modal-in className="flex h-[min(84dvh,760px)] w-[clamp(560px,85vw,1500px)] min-h-0 flex-col overflow-hidden rounded-xl border border-frame-line glass-panel sm:rounded-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        {/* Header */}
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-chip-indigo-bg">
              <FileText className="h-5 w-5 text-chip-indigo-text" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <h2 id="log-viewer-title" className="text-base font-semibold text-ink">
                Application logs
              </h2>
              <p className="truncate font-mono text-xs text-ink-muted">
                {logPath}
                <span className="text-ink-faint"> · {formatSize(sizeBytes)}</span>
              </p>
            </div>
          </div>

          {/* Fills all space between the title and the action buttons. */}
          <div className="relative min-w-[220px] flex-1">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-faint"
              aria-hidden="true"
            />
            <input
              ref={searchInputRef}
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter log lines…"
              aria-label="Filter log lines"
              className="w-full rounded-lg border border-line bg-elevated py-1.5 pl-8 pr-2.5 font-mono text-xs text-ink placeholder:text-ink-faint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            />
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <Tooltip text={live ? "Pause live tail" : "Resume live tail"} block={false}>
            <button
              type="button"
              onClick={() => setLive((value) => !value)}
              aria-pressed={live}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
                live
                  ? "border-status-success-border bg-status-success-bg text-status-success-text"
                  : "border-line bg-elevated text-ink-muted hover:text-ink"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${live ? "bg-emerald-400" : "bg-ink-faint"}`}
                aria-hidden="true"
              />
              {live ? "Live" : "Paused"}
            </button>
            </Tooltip>

            <Tooltip text="Refresh now" block={false}>
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}

              className="rounded-lg border border-line bg-elevated p-2 text-ink-muted hover:text-ink disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            </button>
            </Tooltip>

            <Tooltip text="Copy visible lines" block={false}>
            <button
              type="button"
              onClick={() => void handleCopy()}
              disabled={entries.length === 0}

              className="rounded-lg border border-line bg-elevated p-2 text-ink-muted hover:text-ink disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            >
              <Copy className="h-4 w-4" aria-hidden="true" />
            </button>
            </Tooltip>

            <Tooltip text="Open log file in the default application" block={false}>
            <button
              type="button"
              onClick={() => {
                onOpenExternally?.();
                onClose();
              }}

              className="rounded-lg border border-line bg-elevated p-2 text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            >
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
            </button>
            </Tooltip>

            <Tooltip text="Close" block={false}>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}

              className="rounded-lg p-2 text-ink-muted hover:bg-hover-surface hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
            </Tooltip>
          </div>
        </div>

        {/* Log body */}
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-app px-2 py-2 font-mono text-xs leading-relaxed sm:px-3"
        >
          {/* Sticky column header — glassmorphism panel aligned to the fixed-width row columns. */}
          <div
            className="sticky top-0 z-10 mb-1 flex items-center gap-2 rounded-md border border-line/40 bg-surface/60 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-ink-muted shadow-sm backdrop-blur-md"
            role="row"
          >
            <span className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span className="w-[138px] shrink-0 text-ink/70">Time</span>
            <span className="w-[52px] shrink-0 text-ink/70">Level</span>
            <span className="w-[150px] shrink-0 text-ink/70">Source</span>
            <span className="min-w-0 flex-1 text-ink/70">Message</span>
          </div>

          {error && (
            <p role="alert" className="px-3 py-6 text-center text-xs text-status-danger-text">
              {error}
            </p>
          )}

          {!error && entries.length === 0 && !loading && (
            <p className="px-3 py-6 text-center text-xs text-ink-faint">
              No log entries match the current filters.
            </p>
          )}

          <ul className="space-y-0.5">
            {entries.map((entry, index) => {
              const style = LEVEL_STYLE[entry.level] ?? LEVEL_STYLE.UNKNOWN;
              const Icon = style.icon;
              const isError = entry.level === "ERROR" || entry.level === "CRITICAL";
              return (
                <li
                  key={`${index}-${entry.raw}`}
                  className={`group flex items-start gap-2 rounded px-2 py-1 ${
                    isError ? "bg-status-danger-bg/40" : "hover:bg-elevated/50"
                  }`}
                >
                  <span className={style.className}>
                    <Icon className="mt-0.5 h-3.5 w-3.5" aria-hidden="true" />
                  </span>
                  <span className="w-[138px] shrink-0 text-ink-faint">{entry.timestamp}</span>
                  <span className={`w-[52px] shrink-0 text-[10px] font-semibold ${style.className}`}>
                    {entry.level}
                  </span>
                  <span
                    className="w-[150px] shrink-0 truncate text-ink-faint"
                    title={entry.source}
                  >
                    {entry.source}
                  </span>
                  <span className="min-w-0 flex-1 break-words text-ink-secondary">{entry.message}</span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Footer — hosts the level filters and follow-tail control. */}
        <div className="border-t border-line/60 bg-elevated/50 px-5 py-2.5 text-[11px] text-ink-faint shadow-sm backdrop-blur-md sm:px-6">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            {/* Status pinned to the far left; mr-auto pushes the buttons right so
                the two never interact on the same line. On narrow windows the
                status takes a full row above the buttons. */}
            <span
              className="mr-auto min-w-0 max-w-full basis-full truncate sm:basis-auto"
              role="status"
              aria-atomic="true"
            >
              {loading && entries.length === 0
                ? "Loading log entries…"
                : `${entries.length} of ${formatSize(sizeBytes)} shown`}
            </span>

            <div className="flex items-center gap-2">
              <div
                className="flex overflow-hidden rounded-lg border border-line/60 text-[11px] backdrop-blur-sm"
                role="group"
                aria-label="Filter by log level"
              >
                {LEVEL_FILTERS.map((option) => {
                  const active = level === option.value;
                  const count = option.value ? (levelCounts.get(option.value) ?? 0) : entries.length;
                  return (
                    <button
                      key={option.label}
                      type="button"
                      onClick={() => setLevel(option.value)}
                      aria-pressed={active}
                      title={option.value ? `Show ${option.value} and above` : "Show all levels"}
                      className={`flex items-center gap-1 px-2.5 py-1 font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-400 ${
                        active
                          ? "bg-indigo-600 text-white"
                          : "text-ink-muted hover:bg-elevated hover:text-ink"
                      }`}
                    >
                      {option.label}
                      <span className={active ? "text-chip-indigo-text" : "text-ink-faint"}>
                        {count}
                      </span>
                    </button>
                  );
                })}
              </div>

              <Tooltip text="Scroll to the newest entry" block={false}>
              <button
                type="button"
                onClick={() => setFollowTail(true)}
                aria-pressed={followTail}

                className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
                  followTail
                    ? "border-chip-indigo-border bg-chip-indigo-bg text-chip-indigo-text"
                    : "border-line bg-elevated text-ink-muted hover:text-ink"
                }`}
              >
                <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="hidden sm:inline">Follow tail</span>
              </button>
              </Tooltip>
            </div>

            <span className="hidden items-center gap-1.5 lg:flex">
              <span className="hidden sm:inline">Ctrl + Shift + L</span>
              <span>opens externally</span>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Human-readable byte count, matching the viewer's compact footer style. */
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
