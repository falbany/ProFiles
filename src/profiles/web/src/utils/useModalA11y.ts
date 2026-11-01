import { useEffect } from "react";
import type { KeyboardEvent, RefObject } from "react";

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], video[tabindex], [tabindex]:not([tabindex="-1"])';

export interface UseModalA11yOptions {
  isOpen: boolean;
  /** Called when the user presses Escape inside the dialog. */
  onClose: () => void;
  /** The element carrying `role="dialog"` — Tab is trapped inside it. */
  dialogRef: RefObject<HTMLElement | null>;
  /** Element to focus on open; defaults to the first focusable child. */
  initialFocusRef?: RefObject<HTMLElement | null>;
}

/**
 * Shared dialog a11y: focus trap, initial focus and focus restore
 * (issue #62). Attach the returned handler to the dialog element's
 * `onKeyDown` so Escape and Tab are handled while focus is inside.
 */
export function useModalA11y({
  isOpen,
  onClose,
  dialogRef,
  initialFocusRef,
}: UseModalA11yOptions): (event: KeyboardEvent<HTMLElement>) => void {
  useEffect(() => {
    if (!isOpen) return;

    const previousFocus =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;

    const frame = requestAnimationFrame(() => {
      const target =
        initialFocusRef?.current ??
        dialogRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTOR) ??
        dialogRef.current;
      target?.focus();
    });

    return () => {
      cancelAnimationFrame(frame);
      previousFocus?.focus();
    };
    // Re-run when isOpen flips; refs are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  return (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab") return;

    const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    if (!focusable?.length) return;

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };
}
