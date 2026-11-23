import { useEffect, useRef, useState } from "react";

/** Latest scan-progress snapshot exposed by the hook. */
export interface ScanProgress {
  /** Candidates count from the SSE stream; `null` = degraded or no data yet. */
  progress: number | null;
  /** Whether the server reports a scan running (gates the count segment). */
  inProgress: boolean;
}

const INITIAL_PROGRESS: ScanProgress = { progress: null, inProgress: false };

/**
 * Consume the server's `/api/scan/events` SSE stream while a scan this
 * window initiated is in flight (`active`), exposing live progress for the
 * scan status strip (issue #152).
 *
 * Lifecycle: one `EventSource`, opened when `active` flips true and closed
 * when it flips false or on unmount. The browser reconnects on stream
 * errors on its own; on error we only blank `progress` so the strip falls
 * back silently to elapsed-only — no toasts, no retry logic — and the next
 * successful tick restores the counts. Environments without `EventSource`
 * (test jsdom, exotic browsers) stay inert at the initial state.
 *
 * Visibility is NOT this hook's concern: the caller gates the strip on its
 * own client state (`scanning || initialScanActive`); the `inProgress`
 * flag from the payload only gates the count segment, so cache-only
 * operations (sort reloads) can never paint a previous scan's numbers as
 * progress.
 */
export function useScanProgress(active: boolean): ScanProgress {
  const [state, setState] = useState<ScanProgress>(INITIAL_PROGRESS);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!active || typeof EventSource === "undefined") {
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
      }
      setState(INITIAL_PROGRESS);
      return;
    }

    if (!sourceRef.current) {
      const source = new EventSource("/api/scan/events");
      source.addEventListener("status", (event: MessageEvent<string>) => {
        try {
          const data = JSON.parse(event.data) as {
            progress?: number;
            in_progress?: boolean;
          };
          setState({
            progress: typeof data.progress === "number" ? data.progress : null,
            inProgress: Boolean(data.in_progress),
          });
        } catch {
          // Malformed payload: ignore the tick, keep the last good state.
        }
      });
      source.addEventListener("error", () => {
        // Silent degraded mode; the browser auto-reconnects and the next
        // successful status event restores the counts.
        setState((prev) => ({ ...prev, progress: null }));
      });
      sourceRef.current = source;
    }

    return () => {
      sourceRef.current?.close();
      sourceRef.current = null;
      setState(INITIAL_PROGRESS);
    };
  }, [active]);

  return state;
}
