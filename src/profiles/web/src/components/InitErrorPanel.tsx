import { CircleAlert, RefreshCw } from "lucide-react";

interface InitErrorPanelProps {
  /** Human-readable reason the initial load failed. */
  message: string;
  /** Re-run the initial load (system info + config + initial scan). */
  onRetry: () => void;
  /** Whether a retry is currently in flight. */
  retrying?: boolean;
}

/**
 * Centered recovery panel shown when the app can't complete its initial load.
 *
 * Deliberately not a modal: it sits in the file-list area at normal z-index so
 * the rest of the chrome stays visible and the panel feels like part of the
 * page, matching the design language (surface card, line border, indigo CTA).
 */
export function InitErrorPanel({ message, onRetry, retrying = false }: InitErrorPanelProps) {
  return (
    <div className="flex flex-1 items-center justify-center p-8" role="alert" data-testid="init-error-panel">
      <div className="w-full max-w-sm rounded-xl border border-line bg-surface p-6 text-center shadow-xl">
        <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full border border-status-danger-border bg-status-danger-bg">
          <CircleAlert className="h-5 w-5 text-status-danger-text/80" />
        </div>
        <h3 className="text-sm font-semibold text-ink">Couldn't load the app</h3>
        <p className="mt-1 break-words text-xs text-ink-secondary">{message}</p>
        <button
          type="button"
          onClick={onRetry}
          disabled={retrying}
          className="btn btn-primary mx-auto mt-4 px-3.5 py-1.5 font-semibold shadow-sm"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${retrying ? "animate-spin motion-reduce:animate-none" : ""}`} />
          <span>{retrying ? "Retrying..." : "Retry"}</span>
        </button>
      </div>
    </div>
  );
}
