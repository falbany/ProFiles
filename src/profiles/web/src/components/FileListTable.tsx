import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpDown, FileCode, Loader2 } from "lucide-react";
import type { ScannedFileItem } from "../api/types";

interface ScrollableStickyHeaderItem {
  label: string;
  icon?: React.ReactNode;
  /** flex-grow weight; `1` by default so columns share the width evenly. */
  weight?: number;
}

function ScrollableStickyHeader({ items }: { items: ScrollableStickyHeaderItem[] }) {
  return (
    <div className="sticky top-0 z-10 flex select-none items-center border-b border-line bg-surface font-medium text-ink-muted">
      {items.map((item, i) => (
        <div
          key={i}
          className="flex items-center gap-1.5 truncate px-3 py-2"
          style={{ flex: item.weight ?? 1, minWidth: 0 }}
        >
          {item.icon}
          <span className="truncate">{item.label}</span>
          {i > 0 && <ArrowUpDown className="ml-auto h-3 w-3 shrink-0 opacity-40" />}
        </div>
      ))}
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
  columnHeaders: string[];
  columnNames: string[];
  selectedIndex: number;
  onSelectIndex: (idx: number) => void;
  onLaunch: (file: ScannedFileItem) => void;
  onContextMenu: (e: React.MouseEvent, file: ScannedFileItem, index: number) => void;
  rowColors: [string, string][];
}

/** Fixed row height (px) — `text-xs` + `py-2` lands on 28px. */
const ROW_HEIGHT = 28;
/** Rows rendered above/below the visible window. */
const OVERSCAN = 12;
/** Page size requested from the backend when paging is enabled. */
const PAGE_SIZE = 500;

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
  columnHeaders,
  columnNames,
  selectedIndex,
  onSelectIndex,
  onLaunch,
  onContextMenu,
  rowColors,
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
      }
    });
    observer.observe(el);
    // Seed the initial height synchronously to avoid a first-paint flash.
    setViewportHeight(el.clientHeight || 600);
    return () => observer.disconnect();
  }, []);

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
    return () => {
      el.removeEventListener("scroll", maybeLoadMore);
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
        className: "bg-indigo-600/25 border-l-2 border-indigo-500 text-ink",
        style: {},
      };
    }

    for (const [pattern, color] of rowColors) {
      if (filename.toLowerCase().includes(pattern.toLowerCase())) {
        return {
          className: "hover:bg-elevated border-l-2 text-ink",
          style: { borderLeftColor: color },
        };
      }
    }

    return {
      className: "border-l-2 border-transparent text-ink-secondary hover:bg-elevated/60",
      style: { borderLeftColor: "transparent" },
    };
  };

  // While paging, reserve room past the loaded rows so the user can keep
  // scrolling to trigger the next page instead of hitting a dead end.
  const spacerHeight = (hasMore ? Math.max(total, loadedCount + visibleCount) : total) * ROW_HEIGHT;

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="flex-1 overflow-auto bg-app text-xs"
      data-testid="file-list"
      data-loaded-count={loadedCount}
    >
      <ScrollableStickyHeader
        items={
          [
            { label: "#", icon: <FileCode className="h-3.5 w-3.5" /> },
            ...columnSlots.map(({ key, header }) => ({
              label: header,
              weight: COLUMN_WEIGHTS[key] ?? 1,
            })),
          ] satisfies ScrollableStickyHeaderItem[]
        }
      />

      {loadedCount === 0 ? (
        <div className="p-8 text-center text-ink-faint" data-testid="file-list-empty">
          No matching files found. Click "Scan" to refresh.
        </div>
      ) : (
        /* Spacer reserves the full scroll height. */
        <div className="relative" style={{ height: spacerHeight }}>
          {loadingMore && (
            <div className="pointer-events-none absolute left-1/2 top-2 z-20 -translate-x-1/2">
              <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
            </div>
          )}
          {/* The virtualized window, shifted into position by the transform. */}
          <div style={{ transform: `translateY(${offsetY}px)` }} data-testid="file-list-window">
            {files.slice(startIndex, endIndex).map((file, i) => {
              const idx = startIndex + i;
              const isSelected = idx === selectedIndex;
              const rowStyle = getRowStyle(file.filename, isSelected);
              return (
                <div
                  key={file.path || idx}
                  onClick={() => onSelectIndex(idx)}
                  onDoubleClick={() => onLaunch(file)}
                  onContextMenu={(e) => onContextMenu(e, file, idx)}
                  className={`flex cursor-pointer items-center transition-colors ${rowStyle.className}`}
                  style={{ ...rowStyle.style, height: ROW_HEIGHT }}
                >
                  <div className="shrink-0 px-3 text-right font-mono text-ink-faint">
                    <span className="hidden sm:inline">{idx + 1}</span>
                  </div>
                  {resolvedKeys.map((key, kIdx) => (
                    <div
                      key={kIdx}
                      className="truncate px-3 font-mono"
                      style={{
                        flex: COLUMN_WEIGHTS[key] ?? 1,
                        minWidth: 0,
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
              {loadingMore ? "Loading more… " : ""}
              ({loadedCount} of {grandTotal} loaded)
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export { PAGE_SIZE as SCAN_PAGE_SIZE };
