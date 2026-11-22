import { useRef, useState } from "react";

import { postClientLog } from "../api/client";

export type ToastKind = "info" | "error";

export type ToastMessage = { message: string; kind: ToastKind };

/** Options for showToast; `mirror: false` skips the profiles.log relay. */
export interface ShowToastOptions {
  mirror?: boolean;
}

/**
 * The one toast entry point, injected into every component/hook that needs
 * it. Issue #194: each call is mirrored to `POST /api/logs/client` (DEBUG
 * TOAST record in profiles.log) unless the caller passes `mirror: false` —
 * reserved for server-originated toasts, which the server already logged
 * at the `record_external_event` choke point.
 */
export type ShowToast = (msg: string, kind?: ToastKind, opts?: ShowToastOptions) => void;

/**
 * Transient toast above the action bar (moved verbatim from `App.tsx`,
 * issue #148 PR 2).
 *
 * Info toasts auto-dismiss after 3.5s; error toasts stay a little longer and
 * carry an inline dismiss button, so they never vanish before being read.
 */
export function useToast(): {
  toastMessage: ToastMessage | null;
  showToast: ShowToast;
  dismissToast: () => void;
} {
  const [toastMessage, setToastMessage] = useState<ToastMessage | null>(null);

  const toastTimerRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Show a transient toast above the action bar.
   *
   * Info toasts auto-dismiss after 3.5s; error toasts stay a little longer and
   * carry an inline dismiss button, so they never vanish before being read.
   */
  const showToast: ShowToast = (msg, kind = "info", opts) => {
    if (!msg) return; // never blank an existing toast with an empty message
    setToastMessage({ message: msg, kind });
    // Mirror to profiles.log (issue #194); fire-and-forget, never awaited.
    if (opts?.mirror !== false) postClientLog(msg, kind);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(
      () => setToastMessage(null),
      kind === "error" ? 10000 : 3500,
    );
  };

  const dismissToast = () => {
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    setToastMessage(null);
  };

  return { toastMessage, showToast, dismissToast };
}
