import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { FileCode } from "lucide-react";
import type { ScannedFileItem } from "../api/types";

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

/** Fixed row height (px). `text-xs` cells + `py-2` → 26px; 28 keeps math clean. */
const ROW_HEIGHT = 28;
/** Rows rendered above/below the visible window. */
const OVERSCAN = 12;
/** Page size requested from the backend when paging is enabled. */
const PAGE_SIZE = 500;

/**
 * Windowed (virtualized) file table.
 *
 * A scan can return tens of thousands of rows. Rendering them all as DOM nodes
 * makes the UI unusable, and shipping them all as JSON makes every scan feel
 * slow. This component therefore does both:
 *
 * - **Virtualization** — only rows inside the scroll viewport (plus a small
 *   overscan buffer) are mounted; a spacer keeps the scrollbar meaningful.
 * - **Progressive paging** — rows are fetched in pages of `PAGE_SIZE` from the
 *   backend, and a new page is requested whenever the viewport approaches the
 *   end of the loaded window.
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
  const headers = columnHeaders.length > 0 ? columnHeaders : ["File"];
  const keys = columnNames.length > 0 ? columnNames : ["File"];

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

  // Keep the selected row in view when it changes via keyboard navigation.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el || loadedCount === 0) return;
    const rowTop = selectedIndex * ROW_HEIGHT;
    const rowBottom = rowTop + ROW_HEIGHT;
    const viewTop = el.scrollTop;
    const viewBottom = viewTop + el.clientHeight;
    if (rowTop < viewTop) {
      el.scrollTop = rowTop;
    } else if (rowBottom > viewBottom) {
      el.scrollTop = rowBottom - el.clientHeight;
    }
  }, [selectedIndex, loadedCount]);

  /**
   * Fetch the next page when the user approaches the end of the loaded rows.
   * Uses a plain scroll listener (not React state) so the request starts on
   * the very first relevant scroll event without waiting for a re-render.
   */
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    let cancelled = false;

    const maybeLoadMore = () => {
      if (cancelled) return;
      if (loadingRef.current) return;
      if (!hasMore || !onLoadMore) return;
      const viewEnd = el.scrollTop + el.clientHeight;
      // Distance, in px, from the bottom of the loaded window.
      const distanceToEnd = loadedCount * ROW_HEIGHT - viewEnd;
      if (distanceToEnd < OVERSCAN * ROW_HEIGHT) {
        loadingRef.current = true;
        onLoadMore();
      }
    };

    el.addEventListener("scroll", maybeLoadMore, { passive: true });
    return () => {
      cancelled = true;
      el.removeEventListener("scroll", maybeLoadMore);
    };
  }, [hasMore, onLoadMore, loadedCount]);

  // Release the request lock once the parent has appended (or failed to
  // append) the new page, so subsequent scrolls can trigger another fetch.
  useEffect(() => {
    if (loadingMore) return;
    const t = setTimeout(() => {
      loadingRef.current = false;
    }, 100);
    return () => clearTimeout(t);
  }, [loadingMore, loadedCount]);

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const total = grandTotal;
  const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT) + OVERSCAN * 2;
  // Never render past what is actually loaded — the window is clipped to the
  // loaded page, so the bottom of the scroll area stays reachable.
  const endIndex = Math.min(loadedCount, startIndex + visibleCount);
  const offsetY = startIndex * ROW_HEIGHT;

  const getRowStyle = (filename: string, isSelected: boolean) => {
    if (isSelected) {
      return "bg-indigo-600/25 border-l-2 border-indigo-500 text-ink";
    }
    for (const [pattern, color] of rowColors) {
      if (filename.toLowerCase().includes(pattern.toLowerCase())) {
        return `hover:bg-elevated border-l-2 border-[${color}] text-ink`;
      }
    }
    return "border-l-2 border-transparent hover:bg-elevated/60 text-ink-secondary";
  };

  // The full scroll height assumes every row is loaded; while paging, the
  // spacer grows so the user can keep scrolling to trigger the next page.
  const spacerHeight = hasMore ? Math.max(total, loadedCount + visibleCount) * ROW_HEIGHT : total * ROW_HEIGHT;

  return (
    <div
      ref={scrollRef}
      onScroll={handleScroll}
      className="flex-1 overflow-auto bg-app text-xs"
    >
      <div className="relative" style={{ height: spacerHeight }}>
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 z-10 border-b border-line bg-surface font-medium text-ink-muted">
            <tr>
              <th className="w-8 px-3 py-2"></th>
              {headers.map((h, i) => (
                <th key={i} className="px-3 py-2">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          {loadedCount === 0 ? (
            <tbody>
              <tr>
                <td colSpan={headers.length + 1} className="p-8 text-center text-ink-faint">
                  No matching files found. Click "Scan" to refresh.
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody style={{ transform: `translateY(${offsetY}px)` }}>
              {files.slice(startIndex, endIndex).map((file, i) => {
                const idx = startIndex + i;
                const isSelected = idx === selectedIndex;
                return (
                  <tr
                    key={file.path || idx}
                    style={{ height: ROW_HEIGHT }}
                    onClick={() => onSelectIndex(idx)}
                    onDoubleClick={() => onLaunch(file)}
                    onContextMenu={(e) => onContextMenu(e, file, idx)}
                    className={`cursor-pointer transition-colors ${getRowStyle(file.filename, isSelected)}`}
                  >
                    <td className="px-3 py-2 text-ink-faint">
                      <FileCode className="h-3.5 w-3.5 text-ink-muted" />
                    </td>
                    {keys.map((key, kIdx) => (
                      <td key={kIdx} className="overflow-hidden px-3 py-2 font-mono">
                        {file.column_values[key] || (key === "File" ? file.filename : "-")}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          )}
        </table>
        {hasMore && (
          <div className="pointer-events-none sticky bottom-2 mx-auto w-fit rounded-full border border-line bg-surface-strong px-3 py-1 text-[11px] text-ink-muted shadow">
            Loading more… ({loadedCount} of {grandTotal})
          </div>
        )}
      </div>
    </div>
  );
}

export { PAGE_SIZE as SCAN_PAGE_SIZE };
