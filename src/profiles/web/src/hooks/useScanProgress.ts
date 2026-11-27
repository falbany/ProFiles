import { useScanStatusFeed } from "./useScanStatusFeed";

/** Latest scan-progress snapshot exposed by the hook. */
export interface ScanProgress {
  /** Candidates count from the SSE stream; `null` = degraded or no data yet. */
  progress: number | null;
  /** Whether the server reports a scan running (gates the count segment). */
  inProgress: boolean;
}

/** What the hook shows while the caller hides the strip (`!active`). */
const HIDDEN: ScanProgress = { progress: null, inProgress: false };

/**
 * Consume the server's `/api/scan/events` SSE stream for the scan status
 * strip (issue #152), exposing live progress while a scan this window
 * initiated is in flight (`active`).
 *
 * The `EventSource` itself is the shared feed's (`useScanStatusFeed`,
 * #223) and stays open for the app lifetime — this hook only gates the
 * DISPLAYED values on `active`: while inactive it reports the hidden
 * snapshot (progress null, inProgress false), and live values flow
 * through as soon as `active` turns true. On stream errors the feed
 * blanks `progress` only, so the strip falls back silently to
 * elapsed-only — no toasts, no retry logic — and the next successful
 * tick restores the counts. Environments without `EventSource` (test
 * jsdom, exotic browsers) keep the feed inert at its initial tick.
 *
 * Visibility is NOT this hook's concern: the caller gates the strip on its
 * own client state (`scanning || initialScanActive`); the `inProgress`
 * flag from the payload only gates the count segment, so cache-only
 * operations (sort reloads) can never paint a previous scan's numbers as
 * progress.
 */
export function useScanProgress(active: boolean): ScanProgress {
  const tick = useScanStatusFeed();
  return active ? { progress: tick.progress, inProgress: tick.inProgress } : HIDDEN;
}
