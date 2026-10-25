import { Play, X, XCircle } from "lucide-react";
import { ScanStatusStrip } from "./ScanStatusStrip";

/** Shape of the transient status message exchanged with App. */
export interface ActionBarToast {
  message: string;
  kind: "info" | "error";
}

interface ActionBarProps {
  onExecute: () => void;
  scanning: boolean;
  hasSelection: boolean;
  /** Number of rows currently visible (server total while not filtering). */
  fileCount: number;
  /**
   * Total rows reported by the server; when it differs from `fileCount`
   * (client-side prefilter active), the bar shows "Showing X of N".
   */
  totalCount?: number;
  /** Directory the running scan targets; shown compacted in the scan status. */
  scanningDirectory?: string;
  /** Transient status message; rendered centered above the bar while set. */
  toastMessage?: ActionBarToast | null;
  /** Dismiss the current toast; only used by the inline button on error toasts. */
  onToastDismiss?: () => void;
}

export function ActionBar({
  onExecute,
  scanning,
  hasSelection,
  fileCount,
  totalCount,
  scanningDirectory = "",
  toastMessage,
  onToastDismiss,
}: ActionBarProps) {
  const isError = toastMessage?.kind === "error";

  return (
    <div className="relative flex items-center justify-between border-t border-line bg-surface-glass px-4 py-2.5 text-xs">
      {/* Toast — centered on the action bar both horizontally and
          vertically. Info toasts let pointer events pass through; error
          toasts re-enable them on the inline dismiss button only. */}
      {toastMessage && (
        <div
          role="status"
          aria-live={isError ? "assertive" : "polite"}
          aria-atomic="true"
          className={`absolute left-1/2 top-1/2 z-50 max-w-[min(80vw,640px)] -translate-x-1/2 -translate-y-1/2 rounded-xl border px-4 py-2 text-xs font-medium glass-panel-strong ${
            isError
              ? "pointer-events-auto flex max-w-[min(70vw,560px)] items-center gap-2.5 border-rose-500/30 text-left text-ink"
              : "pointer-events-none max-w-[min(70vw,560px)] text-center text-ink"
          }`}
        >
          {isError ? (
            <>
              <XCircle className="h-3.5 w-3.5 shrink-0 text-rose-400/80" aria-hidden="true" />
              <span className="min-w-0 flex-1">{toastMessage.message}</span>
              {onToastDismiss && (
                <button
                  type="button"
                  onClick={onToastDismiss}
                  aria-label="Dismiss error"
                  className="shrink-0 rounded-md p-0.5 text-rose-300/60 hover:bg-elevated hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400/60 transition-colors"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </>
          ) : (
            toastMessage.message
          )}
        </div>
      )}

      <div className="flex min-w-0 items-center gap-3">
        {scanning && <ScanStatusStrip directory={scanningDirectory} />}
        {totalCount !== undefined && totalCount !== fileCount && (
          <span data-testid="action-bar-count" className="text-ink-muted">
            Showing {fileCount} of {totalCount}
          </span>
        )}
      </div>

      <button
        onClick={onExecute}
        disabled={!hasSelection || scanning}
        className="flex shrink-0 items-center gap-2 rounded-xl border border-emerald-300/50 bg-gradient-to-b from-emerald-400/90 to-emerald-600/90 px-5 py-2 font-semibold text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.35),0_8px_24px_-6px_rgb(16_185_129/0.55)] transition-[filter,box-shadow,transform] hover:-translate-y-px hover:brightness-110 hover:shadow-[inset_0_1px_0_rgb(255_255_255/0.35),0_12px_30px_-6px_rgb(16_185_129/0.7)] disabled:opacity-40 disabled:hover:translate-y-0 disabled:hover:brightness-100 disabled:hover:shadow-[inset_0_1px_0_rgb(255_255_255/0.35),0_8px_24px_-6px_rgb(16_185_129/0.55)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        <Play className="h-3.5 w-3.5 fill-current" />
        <span>Execute</span>
        <kbd className="rounded bg-emerald-800/60 px-1.5 py-0.5 text-[10px] text-emerald-200 shadow-[inset_0_1px_0_rgb(255_255_255/0.12)]">↵</kbd>
      </button>
    </div>
  );
}
