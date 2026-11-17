import { useRef, useState } from "react";

export type ToastMessage = { message: string; kind: "info" | "error" };

/**
 * Transient toast above the action bar (moved verbatim from `App.tsx`,
 * issue #148 PR 2).
 *
 * Info toasts auto-dismiss after 3.5s; error toasts stay a little longer and
 * carry an inline dismiss button, so they never vanish before being read.
 */
export function useToast(): {
  toastMessage: ToastMessage | null;
  showToast: (msg: string, kind?: "info" | "error") => void;
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
  const showToast = (msg: string, kind: "info" | "error" = "info") => {
    if (!msg) return; // never blank an existing toast with an empty message
    setToastMessage({ message: msg, kind });
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
