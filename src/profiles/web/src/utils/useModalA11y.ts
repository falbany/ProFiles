import { useEffect } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from "react";

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
 * `onKeyDown` so Escape is handled while focus is inside.
 *
 * The Tab half of the trap deliberately runs at the window capture level
 * (see the effect), not in this handler: a dialog-level onKeyDown never
 * sees a Tab pressed while focus sits on document.body — e.g. after a
 * backdrop click or an unmounted focused node — and the browser would
 * then happily move focus into the app behind the modal.
 */
export function useModalA11y({
  isOpen,
  onClose,
  dialogRef,
  initialFocusRef,
}: UseModalA11yOptions): (event: ReactKeyboardEvent<HTMLElement>) => void {
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

    // Window-capture Tab trap: owns every Tab press while the modal is
    // open, wherever focus currently sits. One listener per open modal;
    // for stacked dialogs the most recently opened modal's handler runs
    // last and wins, which resolves nesting in favor of the topmost one.
    const trapTab = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const dialog = dialogRef.current;
      if (!dialog) return;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      const inside = active instanceof Node && dialog.contains(active);

      if (!inside) {
        // Focus drifted out: pull it back instead of traversing the app
        // behind the modal.
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
        return;
      }
      if (event.shiftKey && (active === first || active === dialog)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || active === dialog)) {
        event.preventDefault();
        first.focus();
      }
      // Anywhere else inside: leave Tab to native traversal between the
      // dialog's own controls.
    };
    window.addEventListener("keydown", trapTab, true);

    return () => {
      cancelAnimationFrame(frame);
      previousFocus?.focus();
      window.removeEventListener("keydown", trapTab, true);
    };
    // Re-run when isOpen flips; refs are stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  return (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      onClose();
    }
  };
}
