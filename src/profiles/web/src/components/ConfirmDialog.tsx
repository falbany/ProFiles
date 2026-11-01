import { useRef } from "react";
import { AlertTriangle } from "lucide-react";

import { useModalA11y } from "../utils/useModalA11y";

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  /** Body text; `\n` renders as a line break. */
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** When true the confirm button uses the danger styling. */
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * In-app replacement for `window.confirm`, which is a silent no-op inside
 * the desktop webviews (WKWebView / WebKitGTK) — issue #31. Focus starts on
 * the cancel button so a stray Enter/Space can never confirm a destructive
 * action; the focus trap and Escape come from the shared a11y hook.
 */
export function ConfirmDialog({
  isOpen,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const handleDialogKeyDown = useModalA11y({
    isOpen,
    onClose: onCancel,
    dialogRef,
    initialFocusRef: cancelRef,
  });

  if (!isOpen) return null;

  return (
    <div
      className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onKeyDown={handleDialogKeyDown}
        onClick={(e) => e.stopPropagation()}
        className="animate-modal-in w-[400px] max-w-full rounded-2xl border border-frame-line glass-panel p-5"
      >
        <div className="mb-3 flex items-center gap-2.5">
          <span
            className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${
              danger
                ? "bg-status-danger-bg text-status-danger-text"
                : "bg-chip-indigo-bg text-chip-indigo-text"
            }`}
          >
            <AlertTriangle className="h-5 w-5" />
          </span>
          <h2 id="confirm-dialog-title" className="text-sm font-semibold text-ink">
            {title}
          </h2>
        </div>
        <p className="mb-5 whitespace-pre-line text-xs text-ink-secondary">{message}</p>
        <div className="flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            className="min-h-9 rounded-lg border border-line bg-elevated px-3.5 text-sm text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`min-h-9 rounded-lg border px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 ${
              danger
                ? "border-status-danger-border bg-status-danger-bg/30 text-status-danger-text hover:bg-status-danger-bg/60"
                : "btn-primary border-transparent bg-indigo-600 text-white hover:bg-indigo-500"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
