import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

const ROW_HEIGHT = 28;

interface ScanStatusStripProps {
  /** Directory the running scan targets; shown compacted, full path on title. */
  directory: string;
}

interface ScanSkeletonRowsProps {
  columnTemplate: string;
  /** Number of grid columns (including the `#` index column). */
  columnCount: number;
}

/** Seconds elapsed string: `42s` / `2m05s`. */
function formatElapsed(totalSeconds: number): string {
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m${seconds.toString().padStart(2, "0")}s`;
}

/** Trailing segment of the directory, with a `…` prefix when it was cut. */
function shortDirectoryName(directory: string): { label: string; cut: boolean } {
  if (!directory) return { label: "", cut: false };
  const segments = directory.replace(/\\/g, "/").split("/").filter(Boolean);
  if (segments.length === 0) return { label: directory, cut: false };
  return { label: segments[segments.length - 1], cut: segments.length > 1 };
}

/**
 * Slim feedback strip shown directly under the column header while a scan runs.
 *
 * Shows "Scanning <dir> — Ns" with a per-mount second counter — the interval is
 * torn down automatically because the component unmounts when the scan ends.
 * Rendered inside the sticky header group so it stays visible while scrolling.
 */
export function ScanStatusStrip({ directory }: ScanStatusStripProps) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    setElapsed(0);
    const intervalId = window.setInterval(() => {
      setElapsed((seconds) => seconds + 1);
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, []);

  const { label, cut } = shortDirectoryName(directory);

  return (
    <div
      data-testid="scan-status-strip"
      className="flex items-center gap-2 border-b border-line/60 bg-surface px-3 py-1 text-[11px] text-ink-muted"
    >
      <Loader2 className="h-3 w-3 shrink-0 animate-spin text-indigo-400 motion-reduce:animate-none" />
      <span>
        Scanning
        {directory && (
          <>
            {" "}
            <span className="font-mono text-indigo-300/80" title={directory}>
              {cut ? "…/" : ""}
              {label}
            </span>
          </>
        )}
        {" — "}
        <span className="font-mono tabular-nums text-ink-secondary">{formatElapsed(elapsed)}</span>
      </span>
    </div>
  );
}

/**
 * Two shimmer placeholder rows overlaying the top of the stale list.
 *
 * Rendered in normal flow (not sticky) so they scroll away with the content
 * and never obscure rows the user scrolls to — purely a top-of-list hint.
 */
export function ScanSkeletonRows({ columnTemplate, columnCount }: ScanSkeletonRowsProps) {
  return (
    <div aria-hidden="true" className="pointer-events-none opacity-80" data-testid="scan-skeleton-rows">
      {[0, 1].map((row) => (
        <div
          key={row}
          className="grid items-center border-b border-line/40"
          style={{ height: ROW_HEIGHT, gridTemplateColumns: columnTemplate }}
        >
          {Array.from({ length: Math.max(columnCount, 1) }, (_, i) => {
            const width = 50 + ((row * 53 + i * 37) % 32);
            return (
              <div key={i} className="flex items-center px-3">
                <div
                  className="h-2 animate-pulse rounded bg-elevated motion-reduce:animate-none"
                  style={{ width: `${width}%`, animationDelay: `${row * 150 + i * 60}ms`, animationDuration: "1.4s" }}
                />
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
