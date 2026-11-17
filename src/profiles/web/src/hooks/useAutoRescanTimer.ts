import { useEffect, useRef, useState } from "react";

/**
 * Periodic auto-rescan timer (moved verbatim from `App.tsx`, issue #148
 * PR 2). `handleTimerSet` stores the interval in seconds (0 = disabled) and
 * shows the matching toast; the interval effect ticks `scan` every
 * `autoRescanInterval * 1000` ms.
 *
 * `scan` and `showToast` arrive as injected deps, read through a latest-ref
 * so every tick uses the CURRENT directory/extension/filter (issue #34: the
 * interval previously captured the values from when it was enabled) — App's
 * fresh per-render closures are honored without re-arming the timer: the
 * effect keeps its original `[autoRescanInterval]` dep list.
 */
export function useAutoRescanTimer(deps: {
  scan: () => void;
  showToast: (msg: string, kind?: "info" | "error") => void;
}): {
  autoRescanInterval: number;
  handleTimerSet: (intervalSeconds: number) => void;
} {
  // Timer — periodic rescan interval in seconds (0 = disabled).
  const [autoRescanInterval, setAutoRescanInterval] = useState<number>(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Latest deps for the interval callback and the handler (avoids stale
  // closures without re-arming the interval).
  const depsRef = useRef(deps);
  useEffect(() => {
    depsRef.current = deps;
  });

  // Timer — periodic rescan effect. Runs through the injected `scan` (App's
  // handleScanRef wrapper) so every tick uses the CURRENT
  // directory/extension/filter (issue #34: the interval previously captured
  // the values from when it was enabled).
  useEffect(() => {
    if (autoRescanInterval > 0) {
      timerRef.current = setInterval(() => {
        void depsRef.current.scan();
      }, autoRescanInterval * 1000);
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [autoRescanInterval]);

  const handleTimerSet = (intervalSeconds: number) => {
    setAutoRescanInterval(intervalSeconds);
    if (intervalSeconds > 0) {
      depsRef.current.showToast(`Auto-rescan every ${intervalSeconds}s.`);
    } else {
      depsRef.current.showToast("Auto-rescan disabled.");
    }
  };

  return { autoRescanInterval, handleTimerSet };
}
