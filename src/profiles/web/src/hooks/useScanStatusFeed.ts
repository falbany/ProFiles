import { useSyncExternalStore } from "react";

/** Latest scan-status snapshot pushed by the server's `/api/scan/events` stream. */
export interface ScanStatusTick {
  /** Whether the server reports a scan running. */
  inProgress: boolean;
  /** Candidates count from the SSE stream; `null` = degraded or no data yet. */
  progress: number | null;
  /** Directory the reported scan targets (empty when none is advertised). */
  directory: string;
  /** Watch mode (#223): whether the server watches the directory for changes. */
  watching: boolean;
  /** Watch poll interval in seconds; `null` when not watching. */
  watchIntervalS: number | null;
  /** Monotonic watch-cycle sequence; `null` when not watching. */
  watchSeq: number | null;
  /** Last watch-cycle error message; `null` when healthy. */
  watchError: string | null;
}

/** Tick before any `status` event has been accepted (and after the feed closed). */
export const INITIAL_TICK: ScanStatusTick = {
  inProgress: false,
  progress: null,
  directory: "",
  watching: false,
  watchIntervalS: null,
  watchSeq: null,
  watchError: null,
};

/** Raw snake_case `status` payload sent by the server (see Tasks 3-4, #223). */
interface StatusPayload {
  in_progress?: boolean;
  progress?: number;
  directory?: string;
  watching?: boolean;
  watch_interval_s?: number;
  watch_seq?: number;
  watch_error?: string | null;
}

/* --- Module-level singleton store --------------------------------------
 * ONE EventSource for the whole app, shared by every consumer
 * (`useScanProgress`, the watch UI): the connection opens on the first
 * subscriber and closes when the last one unsubscribes — app-lifetime in
 * practice. The tick object is replaced (never mutated) on each accepted
 * `status` event so `useSyncExternalStore` can diff by identity.
 */

let sharedSource: EventSource | null = null;
let sharedTick: ScanStatusTick = INITIAL_TICK;
const subscribers = new Set<() => void>();

function notifySubscribers(): void {
  for (const notify of subscribers) notify();
}

function handleStatusEvent(event: MessageEvent<string>): void {
  try {
    const data = JSON.parse(event.data) as StatusPayload;
    sharedTick = {
      inProgress: Boolean(data.in_progress),
      progress: typeof data.progress === "number" ? data.progress : null,
      directory: typeof data.directory === "string" ? data.directory : "",
      watching: Boolean(data.watching),
      watchIntervalS: typeof data.watch_interval_s === "number" ? data.watch_interval_s : null,
      watchSeq: typeof data.watch_seq === "number" ? data.watch_seq : null,
      watchError: typeof data.watch_error === "string" ? data.watch_error : null,
    };
    notifySubscribers();
  } catch {
    // Malformed payload: ignore the tick, keep the last good state.
  }
}

function handleErrorEvent(): void {
  // Silent degraded mode; the browser auto-reconnects and the next
  // successful status event restores the fields.
  sharedTick = { ...sharedTick, progress: null };
  notifySubscribers();
}

/** Connect on the first subscriber, tear down (and reset) on the last out. */
function subscribeToFeed(onStoreChange: () => void): () => void {
  subscribers.add(onStoreChange);
  if (!sharedSource && typeof EventSource !== "undefined") {
    const source = new EventSource("/api/scan/events");
    source.addEventListener("status", handleStatusEvent);
    source.addEventListener("error", handleErrorEvent);
    sharedSource = source;
  }
  return () => {
    subscribers.delete(onStoreChange);
    if (subscribers.size === 0 && sharedSource) {
      sharedSource.close();
      sharedSource = null;
      // Fresh start for the next consumer set (mirrors #152's reset on
      // teardown): no stale scan numbers can leak into a later mount.
      sharedTick = INITIAL_TICK;
    }
  };
}

const getSnapshot = (): ScanStatusTick => sharedTick;

/**
 * Consume the app-shared `/api/scan/events` SSE feed (issue #223),
 * exposing every field of the server's one-second `status` snapshot:
 * the scan-progress pair (#152) plus the watch fields (watching,
 * interval, cycle sequence, last cycle error).
 *
 * Lifecycle: a single module-level `EventSource` shared by ALL consumers
 * of this hook and of `useScanProgress` — it opens when the first
 * subscriber mounts and closes when the last one unmounts, so it stays
 * open for the app lifetime while any consumer exists. On stream errors
 * only `progress` is blanked (silent degraded mode, browser auto-
 * reconnects); a malformed payload is ignored and the last good tick is
 * kept. Environments without `EventSource` (test jsdom, exotic browsers)
 * stay inert at `INITIAL_TICK` forever.
 */
export function useScanStatusFeed(): ScanStatusTick {
  return useSyncExternalStore(subscribeToFeed, getSnapshot);
}
