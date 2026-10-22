import { Download, Play, Sparkles, X, XCircle } from "lucide-react";

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
  onExport?: () => void;
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
  onExport,
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
          className={`absolute left-1/2 top-1/2 z-50 max-w-[min(80vw,640px)] -translate-x-1/2 -translate-y-1/2 rounded-lg border px-4 py-2 text-xs font-medium shadow-xl backdrop-blur-md ${
            isError
              ? "pointer-events-auto flex max-w-[min(70vw,560px)] items-center gap-2.5 border-rose-500/30 bg-surface-strong text-left text-ink"
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

      <div className="flex items-center gap-3">
        {scanning && (
          <div className="flex items-center gap-2 text-indigo-400">
            <Sparkles className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none" />
            <span>Scanning directory...</span>
          </div>
        )}
        {totalCount !== undefined && totalCount !== fileCount && (
          <span data-testid="action-bar-count" className="text-ink-muted">
            Showing {fileCount} of {totalCount}
          </span>
        )}
        {onExport && (
          <button
            onClick={onExport}
            disabled={fileCount === 0 || scanning}
            className="flex shrink-0 items-center gap-1.5 rounded-md border border-line bg-elevated px-3 py-1.5 text-xs font-medium text-ink-secondary hover:border-indigo-500 hover:text-indigo-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:opacity-40"
          >
            <Download className="h-3.5 w-3.5" />
            <span>Export CSV</span>
          </button>
        )}
      </div>

      <button
        onClick={onExecute}
        disabled={!hasSelection || scanning}
        className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 font-semibold text-white shadow hover:bg-emerald-500 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400"
      >
        <Play className="h-3.5 w-3.5 fill-current" />
        <span>Execute</span>
        <kbd className="rounded bg-emerald-800/60 px-1.5 py-0.5 text-[10px] text-emerald-200">↵</kbd>
      </button>
    </div>
  );
}
