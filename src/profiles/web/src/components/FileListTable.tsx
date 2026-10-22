import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowLeftRight, ArrowUp, ArrowUpDown, FileCode, Info, Loader2, Webhook } from "lucide-react";
import type { ScanSort, ScannedFileItem } from "../api/types";

interface ScrollableStickyHeaderItem {
  label: string;
  icon?: React.ReactNode;
  /** flex-grow weight; `1` by default so columns share the width evenly. */
  weight?: number;
  /** Column name to sort by; omitted for the inert `#` index column. */
  sortKey?: string;
  /** Whether this column currently drives the list order. */
  active?: boolean;
  direction?: ScanSort["direction"];
  onSort?: () => void;
  width?: number;
  canResize?: boolean;
  onResizeBy?: (delta: number) => void;
  onResizeTo?: (width: number) => void;
  defaultWidth?: number;
}

interface ResizePointerState {
  pointerId: number;
  startX: number;
  startWidth: number;
  resizeTo: (width: number) => void;
}

interface ScrollableStickyHeaderProps {
  items: ScrollableStickyHeaderItem[];
  columnTemplate: string;
  resizePointerRef: React.MutableRefObject<ResizePointerState | null>;
  resizeMovedRef: React.MutableRefObject<boolean>;
}

function ScrollableStickyHeader({ items, columnTemplate, resizePointerRef, resizeMovedRef }: ScrollableStickyHeaderProps) {
  return (
    <div
      className="grid select-none items-center border-b border-l-2 border-l-transparent border-line bg-surface font-medium text-ink-muted"
      role="row"
      aria-rowindex={1}
      data-file-list-header
      style={{ gridTemplateColumns: columnTemplate }}
    >
      {items.map((item, i) => {
        const sortable = Boolean(item.onSort && item.sortKey);
        const ariaSort = item.active ? (item.direction === "asc" ? "ascending" : "descending") : "none";
        return (
          <div
            key={i}
            role="columnheader"
            data-column-key={item.sortKey}
            className={`group relative flex items-center gap-1.5 truncate px-3 py-2 ${sortable ? "cursor-pointer hover:text-ink transition-colors" : ""} ${item.active ? "text-ink" : ""}`}
            {...(sortable
              ? {
                  "aria-sort": ariaSort,
                  tabIndex: 0,
                  onClick: item.onSort,
                  onKeyDown: (e: React.KeyboardEvent) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      item.onSort?.();
                    }
                  },
                }
              : {})}
          >
            {item.icon}
            <span className="truncate">{item.label}</span>
            {sortable ? (
              item.active ? (
                item.direction === "asc" ? (
                  <ArrowUp className="ml-auto h-3 w-3 shrink-0 text-indigo-400" />
                ) : (
                  <ArrowDown className="ml-auto h-3 w-3 shrink-0 text-indigo-400" />
                )
              ) : (
                <ArrowUpDown className="ml-auto h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-40 hover:opacity-40" />
              )
            ) : (
              i > 0 && <ArrowUpDown className="ml-auto h-3 w-3 shrink-0 opacity-40" />
            )}
            {item.canResize && item.onResizeBy && (
              <div
                role="separator"
                aria-orientation="vertical"
                aria-label={`Resize ${item.label} column`}
                aria-valuemin={MIN_COLUMN_WIDTH}
                aria-valuemax={MAX_COLUMN_WIDTH}
                aria-valuenow={item.width ?? item.defaultWidth ?? DEFAULT_COLUMN_WIDTH}
                aria-valuetext={`${item.width ?? item.defaultWidth ?? DEFAULT_COLUMN_WIDTH} pixels wide`}
                title="Drag to resize; use arrow keys or click either side to adjust"
                tabIndex={0}
                onClick={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  const wasDragged = resizeMovedRef.current;
                  resizeMovedRef.current = false;
                  if (wasDragged) return;
                  const rect = event.currentTarget.getBoundingClientRect();
                  item.onResizeBy?.(event.clientX < rect.left + rect.width / 2 ? -RESIZE_STEP : RESIZE_STEP);
                }}
                onPointerDown={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  const header = event.currentTarget.parentElement;
                  resizeMovedRef.current = false;
                  resizePointerRef.current = {
                    pointerId: event.pointerId,
                    startX: event.clientX,
                    startWidth: item.width ?? header?.getBoundingClientRect().width ?? item.defaultWidth ?? DEFAULT_COLUMN_WIDTH,
                    resizeTo: item.onResizeTo!,
                  };
                  event.currentTarget.setPointerCapture(event.pointerId);
                }}
                onPointerMove={(event) => {
                  const resize = resizePointerRef.current;
                  if (!resize || resize.pointerId !== event.pointerId) return;
                  const delta = event.clientX - resize.startX;
                  if (Math.abs(delta) > 2) resizeMovedRef.current = true;
                  resize.resizeTo(resize.startWidth + delta);
                }}
                onPointerUp={(event) => {
                  if (resizePointerRef.current?.pointerId === event.pointerId) {
                    event.currentTarget.releasePointerCapture(event.pointerId);
                    resizePointerRef.current = null;
                    window.setTimeout(() => {
                      resizeMovedRef.current = false;
                    }, 0);
                  }
                }}
                onPointerCancel={() => {
                  resizePointerRef.current = null;
                  resizeMovedRef.current = false;
                }}
                onKeyDown={(event) => {
                  event.stopPropagation();
                  if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
                    event.preventDefault();
                    item.onResizeBy?.(event.key === "ArrowLeft" ? -RESIZE_STEP : RESIZE_STEP);
                  } else if (event.key === "Home" || event.key === "End") {
                    event.preventDefault();
                    item.onResizeTo?.(event.key === "Home" ? MIN_COLUMN_WIDTH : MAX_COLUMN_WIDTH);
                  }
                }}
                className="absolute inset-y-0 right-0 z-10 w-3 cursor-col-resize touch-none border-r border-transparent transition-colors hover:border-indigo-400 focus-visible:border-indigo-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

interface FileListTableProps {
  files: ScannedFileItem[];
  /** Total rows reported by the backend, even if not all are loaded yet. */
  totalCount?: number;
  onLoadMore?: () => void;
  /** Whether a page request is currently in flight. */
  loadingMore?: boolean;
  /** Whether a scan is actively running. */
  scanning?: boolean;
  /** Whether at least one scan has completed. */
  hasScanned?: boolean;
  /** Current directory in the controls; branches the empty states. */
  activeDirectory?: string;  /** Whether recursive scanning is on; controls the "Turn off recursive" action. */
  recursive?: boolean;
  /** Re-run the scan with recursive turned off. */
  onDisableRecursive?: () => void;
  /** Open the current directory in the OS file manager. */
  onOpenDirectory?: () => void;
  /** Open the configuration picker (used when no directory is configured). */
  onOpenConfig?: () => void;
  filterText: string;
  onClearFilter: () => void;
  /**
   * Coverage hint for client-side prefiltering (lane #1); `null`/`undefined`
   * renders nothing. Quieter than the scan status bar / error feedback.
   */
  prefilterNote?: string | null;
  columnHeaders: string[];
  columnNames: string[];
  selectedIndex: number;
  onSelectIndex: (idx: number) => void;
  onLaunch: (file: ScannedFileItem) => void;
  onContextMenu: (e: React.MouseEvent, file: ScannedFileItem, index: number) => void;
  rowColors: [string, string][];
  /** Column the list is currently sorted by, or `null` in scan order. */
  sort: ScanSort | null;
  /** Advance the sort state for a column: `asc → desc → none`. */
  onSortChange: (sort: ScanSort | null) => void;
}

/** Fixed row height (px) — `text-xs` + `py-2` lands on 28px. */
const ROW_HEIGHT = 28;
/** Rows rendered above/below the visible window. */
const OVERSCAN = 12;
/** Page size requested from the backend when paging is enabled. */
const PAGE_SIZE = 500;
const MIN_COLUMN_WIDTH = 80;
const MAX_COLUMN_WIDTH = 960;
const DEFAULT_COLUMN_WIDTH = 160;
const RESIZE_STEP = 24;
const INDEX_COLUMN_WIDTH = 44;

/** Column weights so Path gets more room than Type/Version. */
const COLUMN_WEIGHTS: Record<string, number> = { File: 2, Path: 3, FileName: 1, Type: 1, Version: 1 };

/**
 * Windowed (virtualized) file list.
 *
 * A scan can return tens of thousands of rows. Rendering them all as DOM nodes
 * makes the UI unusable, and shipping them all as JSON makes every scan feel
 * slow. This component therefore does both:
 *
 * - **Virtualization** — only rows inside the scroll viewport (plus a small
 *   overscan buffer) are mounted. The scrollbar keeps the full height via a
 *   spacer, so the native scroll position stays meaningful.
 * - **Progressive paging** — rows are fetched in pages of `PAGE_SIZE` from the
 *   backend, and a new page is requested whenever the viewport approaches the
 *   end of the loaded window.
 *
 * Rows are flex containers (not `<tr>`) on purpose: CSS transforms are ignored
 * on table row groups, which would make windowing impossible with a `<table>`.
 */
export function FileListTable({
  files,
  totalCount,
  onLoadMore,
  loadingMore = false,
  scanning = false,
  hasScanned = false,
  activeDirectory = "",
  recursive = false,
  onDisableRecursive,
  onOpenDirectory,
  onOpenConfig,
  filterText,
  onClearFilter,
  prefilterNote,
  columnHeaders,
  columnNames,
  selectedIndex,
  onSelectIndex,
  onLaunch,
  onContextMenu,
  rowColors,
  sort,
  onSortChange,
}: FileListTableProps) {
  const fallbackKeys = ["File"];
  const resolvedKeys = columnNames.length > 0 ? columnNames : fallbackKeys;
  const resolvedHeaders = columnHeaders.length > 0 ? columnHeaders : resolvedKeys;
  const columnSlots = Array.from({ length: Math.max(resolvedKeys.length, resolvedHeaders.length) }, (_, i) => ({
    key: resolvedKeys[i] ?? fallbackKeys[0],
    header: resolvedHeaders[i] ?? resolvedKeys[i] ?? fallbackKeys[0],
  }));

  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(600);
  const [viewportWidth, setViewportWidth] = useState(0);
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>({});
  const resizePointerRef = useRef<ResizePointerState | null>(null);
  const resizeMovedRef = useRef(false);

  const totalColumnWeight = resolvedKeys.reduce((sum, key) => sum + (COLUMN_WEIGHTS[key] ?? 1), 1);
  const resizeColumnTo = (key: string, width: number) => {
    const boundedWidth = Math.min(MAX_COLUMN_WIDTH, Math.max(MIN_COLUMN_WIDTH, Math.round(width)));
    setColumnWidths((current) => ({ ...current, [key]: boundedWidth }));
  };
  const resizeColumnBy = (key: string, delta: number) => {
    const header = Array.from(scrollRef.current?.querySelectorAll<HTMLElement>("[data-column-key]") ?? [])
      .find((element) => element.dataset.columnKey === key);
    const currentWidth = columnWidths[key] ?? header?.getBoundingClientRect().width ?? DEFAULT_COLUMN_WIDTH;
    resizeColumnTo(key, currentWidth + delta);
  };
  const columnTemplate = [
    `${INDEX_COLUMN_WIDTH}px`,
    ...resolvedKeys.map((key) =>
      columnWidths[key]
        ? `${columnWidths[key]}px`
        : `minmax(${MIN_COLUMN_WIDTH}px, ${COLUMN_WEIGHTS[key] ?? 1}fr)`,
    ),
  ].join(" ");

  /** Guards against firing multiple concurrent page requests. */
  const loadingRef = useRef(false);

  const loadedCount = files.length;
  const grandTotal = totalCount ?? loadedCount;
  const hasMore = loadedCount < grandTotal;

  // Track viewport size so the rendered window adapts to resizes.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setViewportHeight(entry.contentRect.height);
        setViewportWidth(entry.contentRect.width);
      }
    });
    observer.observe(el);
    // Seed the initial height synchronously to avoid a first-paint flash.
    setViewportHeight(el.clientHeight || 600);
    setViewportWidth(el.clientWidth || 0);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || selectedIndex < 0 || selectedIndex >= loadedCount) return;
    const headerHeight = el.querySelector<HTMLElement>("[data-file-list-header]")?.offsetHeight ?? 0;
    const rowTop = headerHeight + selectedIndex * ROW_HEIGHT;
    const rowBottom = rowTop + ROW_HEIGHT;
    let nextScrollTop = el.scrollTop;
    if (rowTop < el.scrollTop + headerHeight) {
      nextScrollTop = rowTop - headerHeight;
    } else if (rowBottom > el.scrollTop + el.clientHeight) {
      nextScrollTop = rowBottom - el.clientHeight;
    }
    if (nextScrollTop !== el.scrollTop) {
      el.scrollTop = nextScrollTop;
      setScrollTop(nextScrollTop);
    }
  }, [selectedIndex, loadedCount]);

  /**
   * Fetch the next page when the user approaches the end of the loaded rows.
   *
   * Runs as a **scroll listener** so the request starts immediately, and again
   * as a **render-time check** so the list still fills if the scroll event was
   * missed (e.g. a jump straight to the bottom of the scrollbar).
   */
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const maybeLoadMore = () => {
      if (loadingRef.current) return;
      if (!hasMore || !onLoadMore) return;
      const viewEnd = el.scrollTop + el.clientHeight;
      // Distance, in px, from the bottom of the loaded window.
      const distanceToEnd = loadedCount * ROW_HEIGHT - viewEnd;
      if (distanceToEnd < OVERSCAN * ROW_HEIGHT) {
        loadingRef.current = true;
        window.setTimeout(() => {
          loadingRef.current = false;
        }, 200);
        onLoadMore();
      }
    };

    el.addEventListener("scroll", maybeLoadMore, { passive: true });
    // Global event: also listen on window so load-more triggers even when
    // scrolling is delegated to a parent container (not the element itself).
    window.addEventListener("scroll", maybeLoadMore, { passive: true });
    return () => {
      el.removeEventListener("scroll", maybeLoadMore);
      window.removeEventListener("scroll", maybeLoadMore);
    };
  }, [files, hasMore, onLoadMore, loadedCount]);

  // Render-time fallback: covers the case where the appended page still leaves
  // the viewport near the end (e.g. a large jump) with no further scroll.
  useEffect(() => {
    if (loadingRef.current) return;
    if (!hasMore || !onLoadMore) return;
    const distanceToEnd = loadedCount * ROW_HEIGHT - (scrollTop + viewportHeight);
    if (distanceToEnd < OVERSCAN * ROW_HEIGHT) {
      onLoadMore();
    }
  });

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const total = grandTotal;
  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT) + OVERSCAN * 2;
  // Never render past what is actually loaded — the window is clipped to the
  // loaded page so the bottom of the list stays reachable while paging.
  const endIndex = Math.min(loadedCount, startIndex + visibleCount);
  const offsetY = startIndex * ROW_HEIGHT;

  const getRowStyle = (filename: string, isSelected: boolean): { className: string; style: React.CSSProperties } => {
    if (isSelected) {
      return {
        className: "bg-indigo-600/25 border-l-4 border-indigo-500 text-ink",
        style: {},
      };
    }

    for (const [pattern, color] of rowColors) {
      const matches = filename.toLowerCase().includes(pattern.toLowerCase());
      if (matches) {
        return {
          className: "hover:bg-elevated border-l-4 text-ink",
          style: { borderLeftColor: color, borderLeftWidth: '4px' as const },
        };
      }
    }

    return {
      className: "border-l-4 border-transparent text-ink-secondary hover:bg-elevated/60",
      style: { borderLeftColor: 'transparent', borderLeftWidth: '4px' as const },
    };
  };

  // While paging, reserve room past the loaded rows so the user can keep
  // scrolling to trigger the next page instead of hitting a dead end.
  const spacerHeight = (hasMore ? Math.max(total, loadedCount + visibleCount) : total) * ROW_HEIGHT;

  /** Shared styling for the empty-state action buttons (row-button idiom). */
  const emptyActionButtonClass =
    "rounded-md border border-line bg-elevated px-3 py-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors";

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="flex-1 overflow-auto bg-app text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-500 focus-visible:outline-offset-[-2px]"
      data-testid="file-list"
      data-loaded-count={loadedCount}
      aria-busy={scanning}
      role="grid"
      aria-label="Discovered files"
      aria-rowcount={Math.max(grandTotal, loadedCount === 0 ? 1 : 0) + 1}
      aria-colcount={resolvedKeys.length + 1}
      aria-activedescendant={loadedCount > 0 ? `file-row-${selectedIndex}` : undefined}
      tabIndex={0}
    >
      <div className="sticky top-0 z-10" role="presentation">
        <ScrollableStickyHeader
          columnTemplate={columnTemplate}
          resizePointerRef={resizePointerRef}
          resizeMovedRef={resizeMovedRef}
          items={
          [
            { label: "#", icon: <FileCode className="h-3.5 w-3.5" /> },
            ...columnSlots.map(({ key, header }) => ({
              label: header,
              weight: COLUMN_WEIGHTS[key] ?? 1,
              width: columnWidths[key],
              defaultWidth: Math.min(
                MAX_COLUMN_WIDTH,
                Math.max(
                  MIN_COLUMN_WIDTH,
                  Math.round(
                    ((viewportWidth - INDEX_COLUMN_WIDTH) * (COLUMN_WEIGHTS[key] ?? 1)) / totalColumnWeight,
                  ),
                ),
              ),
              canResize: true,
              onResizeBy: (delta: number) => resizeColumnBy(key, delta),
              onResizeTo: (width: number) => resizeColumnTo(key, width),
              sortKey: key,
              active: sort?.column === key,
              direction: sort?.direction,
              onSort: () => {
                if (sort?.column !== key) {
                  onSortChange({ column: key, direction: "asc" });
                } else if (sort.direction === "asc") {
                  onSortChange({ column: key, direction: "desc" });
                } else {
                  onSortChange(null);
                }
              },
            })),
          ] satisfies ScrollableStickyHeaderItem[]
        }
        />
      </div>

      {/* Prefilter coverage hint — inline (scrolls), visually quieter than the
          scan status bar and the empty-state feedback above. */}
      {prefilterNote && loadedCount > 0 && (
        <div
          role="note"
          data-testid="prefilter-note"
          className="flex items-center gap-1.5 border-b border-line/40 bg-surface px-3 py-1 text-[11px] text-ink-faint"
        >
          <Info className="h-3 w-3 shrink-0 text-ink-faint" aria-hidden="true" />
          <span className="min-w-0 truncate">{prefilterNote}</span>
        </div>
      )}

      {loadedCount === 0 ? (
        <div role="row" aria-rowindex={2} data-testid="file-list-empty">
          <div role="gridcell" aria-colspan={resolvedKeys.length + 1} className="p-8 text-center text-ink-faint">
            {scanning ? (
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin text-indigo-400 motion-reduce:animate-none" />
                <span>Scanning files...</span>
              </div>
            ) : !activeDirectory.trim() && onOpenConfig ? (
              <div className="flex flex-col items-center gap-3">
                <span>Select a directory first.</span>
                <button
                  type="button"
                  onClick={onOpenConfig}
                  className={emptyActionButtonClass}
                >
                  Choose configuration
                </button>
              </div>
            ) : !hasScanned ? (
              <span>Select a directory and scan to find files.</span>
            ) : filterText.trim() ? (
              <div className="flex flex-col items-center gap-3">
                <span>No files match “{filterText}”.</span>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  <button
                    type="button"
                    onClick={onClearFilter}
                    className={emptyActionButtonClass}
                  >
                    Clear filter
                  </button>
                  {recursive && onDisableRecursive && (
                    <button
                      type="button"
                      onClick={onDisableRecursive}
                      className={emptyActionButtonClass}
                    >
                      Turn off recursive
                    </button>
                  )}
                  {onOpenDirectory && (
                    <button
                      type="button"
                      onClick={onOpenDirectory}
                      className={emptyActionButtonClass}
                    >
                      Open directory
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <span>No files found for the current directory and extension.</span>
                <div className="flex flex-wrap items-center justify-center gap-2">
                  {recursive && onDisableRecursive && (
                    <button
                      type="button"
                      onClick={onDisableRecursive}
                      className={emptyActionButtonClass}
                    >
                      Turn off recursive
                    </button>
                  )}
                  {onOpenDirectory && (
                    <button
                      type="button"
                      onClick={onOpenDirectory}
                      className={emptyActionButtonClass}
                    >
                      Open directory
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Spacer reserves the full scroll height. */
        <div className="relative" style={{ height: spacerHeight }} role="rowgroup">
          {loadingMore && (
            <div className="pointer-events-none absolute left-1/2 top-2 z-20 -translate-x-1/2" aria-hidden="true">
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
            </div>
          )}
          {/* The virtualized window, shifted into position by the transform. */}
          <div style={{ transform: `translateY(${offsetY}px)` }} data-testid="file-list-window" role="presentation">
            {files.slice(startIndex, endIndex).map((file, i) => {
              const idx = startIndex + i;
              const isSelected = idx === selectedIndex;
              const rowStyle = getRowStyle(file.filename, isSelected);
              return (
                <div
                  key={file.path || idx}
                  id={`file-row-${idx}`}
                  data-row-index={idx}
                  role="row"
                  aria-rowindex={idx + 2}
                  aria-selected={isSelected}
                  onClick={() => {
                    onSelectIndex(idx);
                    scrollRef.current?.focus();
                  }}
                  onDoubleClick={() => onLaunch(file)}
                  onContextMenu={(e) => onContextMenu(e, file, idx)}
                  className={`grid cursor-pointer items-center transition-colors ${rowStyle.className}`}
                  style={{ ...rowStyle.style, height: ROW_HEIGHT, gridTemplateColumns: columnTemplate }}
                >
                  <div className="flex items-center justify-end gap-1 px-3 font-mono text-ink-faint">
                    {file.has_hook && (
                      <span
                        title={file.hook_pattern ? `Launch workflow: ${file.hook_pattern}` : "Launch workflow configured"}
                        aria-label="Workflow hook attached"
                        className="inline-flex items-center text-amber-500/80 hover:text-amber-400"
                      >
                        <Webhook className="h-3 w-3 shrink-0" />
                      </span>
                    )}
                    <span className="hidden sm:inline">{idx + 1}</span>
                  </div>
                  {resolvedKeys.map((key, kIdx) => (
                    <div
                      key={kIdx}
                      role="gridcell"
                      data-column-key={key}
                      className="truncate px-3 font-mono"
                      style={{
                        minWidth: MIN_COLUMN_WIDTH,
                      }}
                      title={key === "Path" ? file.path : undefined}
                    >
                      {file.column_values[key] || (key === "File" ? file.filename : "-")}
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
          {hasMore && (
            <div
              className="pointer-events-none absolute bottom-2 left-1/2 -translate-x-1/2 rounded-full border border-line bg-surface-strong px-3 py-1 text-[11px] text-ink-muted shadow"
              data-testid="file-list-paging"
            >
              {loadingMore ? (
                <ArrowLeftRight className="mr-1.5 h-4 w-4 animate-spin motion-reduce:animate-none text-ink-muted" />
              ) : null}
              ({loadedCount} of {grandTotal} loaded)
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export { PAGE_SIZE as SCAN_PAGE_SIZE };
