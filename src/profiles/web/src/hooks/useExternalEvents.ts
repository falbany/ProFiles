import { useEffect, useRef } from "react";
import { fetchNotifications } from "../api/client";
import type { ExternalEvent } from "../api/types";
import type { ShowToast } from "./useToast";

/** Poll interval for server-side UI events (config handoff toasts). */
const NOTIFICATION_POLL_MS = 4000;

/**
 * Config handoff notifications (issue #4): when a second ProFiles launch
 * double-clicks a .profiles file, the running instance applies it
 * server-side and buffers an event. A light poll surfaces the event as a
 * toast and re-fetches the config + rescans when the event says one was
 * applied. Refs keep the interval callback reading the latest handlers.
 *
 * Extracted from `App.tsx` (issue #148 PR 2): the re-apply and the toast
 * arrive as injected `deps`, read through a latest-ref (the former
 * `externalConfigApplyRef` pattern generalized to the whole deps bag) so
 * App's fresh per-render closures are honored without re-arming the
 * interval — the two effects keep their original dep lists.
 */
export function useExternalEvents(deps: {
  onConfigApplied: () => Promise<void>;
  showToast: ShowToast;
}): void {
  const lastEventIdRef = useRef(0);
  // Latest deps for the interval callback (avoids stale closures — the
  // `externalConfigApplyRef` pattern from App.tsx generalized to the whole
  // deps bag).
  const depsRef = useRef(deps);
  useEffect(() => {
    depsRef.current = deps;
  });
  useEffect(() => {
    const poll = async () => {
      let events: ExternalEvent[] = [];
      try {
        const res = await fetchNotifications(lastEventIdRef.current);
        events = res.events;
      } catch {
        return; // server unreachable — retry silently on the next tick
      }
      for (const evt of events) {
        lastEventIdRef.current = Math.max(lastEventIdRef.current, evt.id);
        if (evt.config_applied) {
          try {
            await depsRef.current.onConfigApplied();
          } catch {
            // Re-applying is best-effort; the toast still explains what happened.
          }
        }
        // mirror: false — the server already logged this event as a TOAST
        // record at the record_external_event choke point (issue #194);
        // relaying it back through POST /api/logs/client would duplicate it.
        depsRef.current.showToast(evt.message, "info", { mirror: false });
      }
    };
    const id = setInterval(() => void poll(), NOTIFICATION_POLL_MS);
    return () => clearInterval(id);
  }, []);
}
