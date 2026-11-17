import { useEffect, useRef, useState } from "react";

/** Theme values — the only two valid persisted themes (#129: a stored
"auto" or garbage falls back to "dark"; matchMedia-driven "auto" is a
non-goal follow-up issue). */
export type Theme = "dark" | "light";

const STORAGE_KEY = "profiles-theme";

/** Stored preference reader for the lazy initializer — try/catch guarded
(storage may be unavailable), and only "dark"/"light" are accepted. */
function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "dark" || stored === "light" ? stored : "dark";
  } catch {
    /* storage may be unavailable */
    return "dark";
  }
}

/**
 * Theme state for the app (issue #148 PR 5), extracted from `App.tsx` — and
 * the fix for issue #129, which changes exactly two behaviors:
 *
 * 1. RESTORE at startup: the lazy `useState` initializer reads
 *    `localStorage["profiles-theme"]` (try/catch; validated — anything but
 *    "dark"/"light", including "auto" or an unreadable store, falls back to
 *    "dark"). Today every mount starts "dark" until the config loads; now
 *    the stored preference wins between mount and config load (the config
 *    stays source of truth AFTER load).
 * 2. LEAK KILLED: config-load/reload themes are session trials — they must
 *    not overwrite the stored preference. Persistence is call-site-
 *    controlled via `applyTheme(next, { persist })` (writes localStorage at
 *    CALL time, never inside the `setTheme` updater — an updater write would
 *    be StrictMode-impure), replacing App's always-persist effect.
 *
 * Provenance (binding — every App call site maps to exactly one row):
 *
 * | App call site                        | persist | why                      |
 * |--------------------------------------|---------|--------------------------|
 * | `initializeFromConfig`               | true    | config is source of truth at startup |
 * | user toggles (shortcut + StatusBar)  | true    | a user choice is a preference |
 * | `handleConfigLoaded` (trial)         | false   | #129: session trial must not steal the stored pref |
 * | `handleReloadConfig` (trial)         | false   | same |
 *
 * Staleness ruling (why `toggleTheme` reads `themeRef` instead of capturing
 * render-scope `theme`): the toggles reach the handler through
 * `useGlobalShortcuts`'s subscription-time capture with `theme` NOT in its
 * re-subscribe dep list, so a captured render-scope `theme` could go stale
 * and flip the toggle the wrong way. `themeRef` is kept current by a
 * per-render effect (the `useAutoRescanTimer` depsRef idiom) and read at
 * CALL time — the same immunity as today's `setTheme((prev) => …)` functional
 * updater, without an impure updater.
 *
 * EVERY localStorage write goes through `applyTheme`/`toggleTheme` — App's
 * always-persist effect is deleted in Task 2, making these the only writers
 * (grep gate in Task 2).
 */
export function useTheme(): {
  theme: Theme;
  applyTheme: (next: Theme, opts: { persist: boolean }) => void;
  toggleTheme: (opts: { persist: boolean }) => void;
} {
  // Theme — restored from localStorage at startup (issue #129: the stored
  // preference survives the mount-to-config-load window; invalid or
  // unreadable values fall back to "dark").
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  // Current theme for call-time reads (toggles may arrive through a handler
  // captured at subscription time — see the staleness ruling above).
  const themeRef = useRef<Theme>(theme);
  useEffect(() => {
    themeRef.current = theme;
  });

  // Apply the theme attribute on every change (moved verbatim from App.tsx).
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const applyTheme = (next: Theme, opts: { persist: boolean }) => {
    setTheme(next);
    if (opts.persist) {
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* storage may be unavailable */
      }
    }
  };

  const toggleTheme = (opts: { persist: boolean }) => {
    applyTheme(themeRef.current === "dark" ? "light" : "dark", opts);
  };

  return { theme, applyTheme, toggleTheme };
}
