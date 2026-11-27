import { useCallback, useEffect, useRef, useState } from "react";
import { setWatchMode } from "../api/client";
import { useScanStatusFeed } from "./useScanStatusFeed";

/** Injected dependencies of `useWatchMode` — App's fresh per-render closures. */
export interface WatchModeDeps {
  /** App's handleScan wrapper (latest-ref pattern); fires the rescan on a seq bump. */
  scan: () => void;
  /** UI toast sink (info by default; watch errors and failures use "error"). */
  showToast: (msg: string, kind?: "info" | "error") => void;
  /** True while the client-side scan fetch is in flight, read fresh per tick. */
  isScanning: () => boolean;
}

/** Watch-mode state and the toggle handler consumed by App/SearchBar (#223). */
export interface WatchMode {
  /** Whether watch mode is currently on (client-caused or server truth). */
  watching: boolean;
  /** Server-reported adaptive poll interval in seconds; null when unknown. */
  watchIntervalS: number | null;
  /** Enable/disable watch mode; applies the response, toasts once, never throws. */
  handleWatchSet: (enable: boolean) => Promise<void>;
}

/**
 * Watch-mode toggle driven by the shared `/api/scan/events` feed (issue
 * #223). Semantics pinned by the spec:
 *
 * - **Toggle state derives from the feed**: the local `watching` state is
 *   seeded from ticks (`tick.watching`); the server payload is the truth
 *   and the toggle renders it. Client-caused transitions (`handleWatchSet`)
 *   set the state immediately from the RESPONSE; server-driven ones flow
 *   from ticks.
 * - **Seq edge-trigger**: the first tick carrying a non-null `watch_seq`
 *   while not watching records the baseline and never fires. On a seq BUMP
 *   while watching: call `deps.scan()` once. A bump observed mid-scan sets
 *   a pending flag that drains exactly ONE trailing scan on the first
 *   subsequent tick where `tick.inProgress` is false and `isScanning()` is
 *   false — server-side progress is the settle signal, so App's
 *   `handleScan` needs no wiring. Seqs are consumed as they fire, so a
 *   re-delivered snapshot never refires.
 * - **Server-driven untoggle**: `watching:false` the client did not cause
 *   un-toggles silently when `watch_error` is empty, with ONE error toast
 *   per DISTINCT message otherwise (dedupe by message string; a new
 *   message toasts again).
 * - **Client-caused transitions toast exactly once** ("Watching for
 *   changes." / "Watch disabled."). An intent guard keeps a client-caused
 *   disable from being re-toasted by the next tick's `watching:false`. On
 *   fetch rejection: one error toast prefixed "Watch failed: " and the
 *   toggle stays off.
 */
export function useWatchMode(deps: WatchModeDeps): WatchMode {
  const tick = useScanStatusFeed();

  // Toggle state — seeded/reconciled from ticks, set immediately from the
  // response on client-caused transitions.
  const [watching, setWatching] = useState(false);
  const watchingRef = useRef(watching);
  /** Last processed watch cycle seq; null until the baseline is recorded. */
  const lastSeqRef = useRef<number | null>(null);
  /** A bump fired mid-scan: one trailing scan waits for a settled tick. */
  const pendingRef = useRef(false);
  /** Message of the last watch error we toasted (distinct-message dedupe). */
  const lastErrorRef = useRef<string | null>(null);
  /** Client-caused transition marker, consumed by the next tick (intent guard). */
  const intentRef = useRef<"enable" | "disable" | null>(null);

  // Latest deps for the tick effect and the handler (mirrors
  // useAutoRescanTimer): fresh closures honored without re-subscribing.
  const depsRef = useRef(deps);
  useEffect(() => {
    depsRef.current = deps;
  });

  // Process every accepted status tick: reconcile the toggle with the
  // server truth, then run the seq edge-trigger. Ticks coalesce if several
  // arrive between renders (the store keeps only the latest snapshot) —
  // at one tick per second the edge semantics are unaffected.
  useEffect(() => {
    // One-shot intent guard: a client-caused transition is confirmed (or
    // contradicted) by the next tick and must not re-toast from it.
    const intent = intentRef.current;
    intentRef.current = null;
    // Pre-tick watching state: distinguishes an armed session (client-caused
    // enable) from a feed-seeded one — the baseline swallows the seq the
    // passive hook first observes (page reload while the server watches).
    const wasWatching = watchingRef.current;

    // Reconciliation: the server payload is the truth.
    if (tick.watching !== wasWatching) {
      watchingRef.current = tick.watching;
      setWatching(tick.watching);
      if (!tick.watching) {
        // Watch gone: any deferred trailing scan is moot now.
        pendingRef.current = false;
        // Server-driven untoggle: silent when healthy, one error toast per
        // distinct message otherwise. A client-caused disable (intent
        // guard) never toasts from its own confirmation tick.
        if (
          wasWatching &&
          intent !== "disable" &&
          tick.watchError &&
          tick.watchError !== lastErrorRef.current
        ) {
          lastErrorRef.current = tick.watchError;
          depsRef.current.showToast(tick.watchError, "error");
        }
      }
    }

    if (tick.watchSeq === null) return;

    // Drain a bump deferred mid-scan: the first settled tick (server-side
    // progress done AND client idle) fires the ONE trailing scan. Newer
    // bumps coalesce into the pending seq while still busy.
    if (pendingRef.current) {
      lastSeqRef.current = tick.watchSeq;
      if (!tick.inProgress && !depsRef.current.isScanning()) {
        pendingRef.current = false;
        depsRef.current.scan();
      }
      return;
    }

    // Passive (not watching before this tick): record the baseline for the
    // seq we observe — never fire on it.
    if (!wasWatching) {
      lastSeqRef.current = tick.watchSeq;
      return;
    }

    // The watch just stopped on this tick: never fire for it.
    if (!tick.watching) return;

    if (tick.watchSeq !== lastSeqRef.current) {
      lastSeqRef.current = tick.watchSeq;
      if (depsRef.current.isScanning()) {
        pendingRef.current = true;
      } else {
        depsRef.current.scan();
      }
    }
  }, [tick]);

  const handleWatchSet = useCallback(async (enable: boolean) => {
    try {
      const res = await setWatchMode({ enabled: enable });
      // Client-caused transition: apply the RESPONSE immediately.
      watchingRef.current = res.watching;
      setWatching(res.watching);
      intentRef.current = enable ? "enable" : "disable";
      depsRef.current.showToast(enable ? "Watching for changes." : "Watch disabled.");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      depsRef.current.showToast(`Watch failed: ${message}`, "error");
    }
  }, []);

  return { watching, watchIntervalS: tick.watchIntervalS, handleWatchSet };
}
