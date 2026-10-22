import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

interface ScanStatusStripProps {
  /** Directory the running scan targets; shown compacted, full path on title. */
  directory: string;
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
 * Inline scan status rendered inside the ActionBar's left cluster.
 *
 * Shows "Scanning <dir> — Ns" with a per-mount second counter — the interval
 * is torn down automatically because the component unmounts when the scan
 * ends. Compact inline presentation (icon + text, no strip borders or pinned
 * header behavior) sized for a single-bar height; the spinner is the motion
 * cue and is disabled under `prefers-reduced-motion`.
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
      className="flex min-w-0 items-center gap-1.5 text-[11px] text-ink-muted"
    >
      <Loader2 className="h-3 w-3 shrink-0 animate-spin text-indigo-400 motion-reduce:animate-none" aria-hidden="true" />
      <span className="min-w-0 truncate">
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
