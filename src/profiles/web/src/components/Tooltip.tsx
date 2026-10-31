import { cloneElement, useCallback, useEffect, useId, useRef, useState, type ReactElement } from "react";
import { createPortal } from "react-dom";

type Placement = "top" | "bottom" | "left" | "right";

type TooltipProps = {
  /** Plain text or rich content shown on hover. */
  text: React.ReactNode;
  children: ReactElement;
  /** Allow the wrapper to grow with a flex parent (`flex-1`, `w-full`, …). */
  block?: boolean;
  /** Preferred placement; the actual side flips automatically when there is no room. */
  placement?: Placement;
  /**
   * Keep the bubble hidden while true — used by combobox callers so the
   * tooltip can never overlay their unfolded list (issue #53).
   */
  suppress?: boolean;
};

/** Breathing room kept between the bubble and the viewport edges. */
const VIEWPORT_MARGIN = 8;
/** Gap between the trigger and the bubble. */
const OFFSET = 8;
/** Hover-intent delay before a pointer-triggered bubble appears (focus is instant). */
const HOVER_DELAY_MS = 400;

/** Opposite side used when the preferred one has no room in the window. */
const FLIPPED: Record<Placement, Placement> = {
  top: "bottom",
  bottom: "top",
  left: "right",
  right: "left",
};

/** Arrow anchors for each resolved side. */
const ARROW_CLASS: Record<Placement, string> = {
  top: "-bottom-1 left-1/2 -translate-x-1/2",
  bottom: "-top-1 left-1/2 -translate-x-1/2",
  left: "-right-1 top-1/2 -translate-y-1/2",
  right: "-left-1 top-1/2 -translate-y-1/2",
};

/** Border sides the arrow squares off, mirroring its rounded position. */
const ARROW_BORDERS: Record<Placement, string> = {
  top: "border-b border-r",
  bottom: "border-t border-l",
  left: "border-t border-r",
  right: "border-b border-l",
};

type Box = { top: number; bottom: number; left: number; right: number; width: number; height: number };
type Size = { w: number; h: number };

/** Does the bubble fit on that side without hanging out of the window? */
const fits = (side: Placement, rect: Box, size: Size): boolean => {
  switch (side) {
    case "top":
      return rect.top - OFFSET - size.h >= VIEWPORT_MARGIN;
    case "bottom":
      return rect.bottom + OFFSET + size.h <= window.innerHeight - VIEWPORT_MARGIN;
    case "left":
      return rect.left - OFFSET - size.w >= VIEWPORT_MARGIN;
    default:
      return rect.right + OFFSET + size.w <= window.innerWidth - VIEWPORT_MARGIN;
  }
};

/**
 * Shift needed along the bubble's main axis to stay inside the window. Returns 0
 * when already clear, so ordinary tooltips sit patiently above their trigger.
 */
const computeNudge = (
  side: Placement,
  rect: Box,
  size: Size,
): { x: number; y: number } => {
  if (side === "top" || side === "bottom") {
    const left = rect.left + rect.width / 2 - size.w / 2;
    const maxLeft = window.innerWidth - size.w - VIEWPORT_MARGIN;
    const desired = Math.min(Math.max(left, VIEWPORT_MARGIN), Math.max(VIEWPORT_MARGIN, maxLeft));
    return { x: desired - left, y: 0 };
  }
  const top = rect.top + rect.height / 2 - size.h / 2;
  const maxTop = window.innerHeight - size.h - VIEWPORT_MARGIN;
  const desired = Math.min(Math.max(top, VIEWPORT_MARGIN), Math.max(VIEWPORT_MARGIN, maxTop));
  return { x: 0, y: desired - top };
};

const Tooltip: React.FC<TooltipProps> = ({
  text,
  children,
  block = true,
  placement = "top",
  suppress = false,
}) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const bubbleRef = useRef<HTMLSpanElement>(null);
  const tooltipId = useId();
  const hoverTimerRef = useRef<number | null>(null);

  const [visible, setVisible] = useState(false);
  const [side, setSide] = useState<Placement>(placement);
  const [nudge, setNudge] = useState({ x: 0, y: 0 });
  /** Viewport position of the resolved bubble box (see `measure`). */
  const [bubblePos, setBubblePos] = useState({ left: -9999, top: -9999 });

  const clearHoverTimer = () => {
    if (hoverTimerRef.current !== null) {
      window.clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
  };

  /** Suppression (unfolded combobox list) always wins, immediately. */
  useEffect(() => {
    if (suppress) {
      clearHoverTimer();
      setVisible(false);
    }
  }, [suppress]);

  // Never leave a pending reveal timer across unmounts.
  useEffect(() => () => clearHoverTimer(), []);

  /**
   * Anchor the bubble in viewport coordinates. The bubble renders through a
   * portal with `position: fixed`, so an `overflow-hidden` ancestor (modal
   * panel, scroll container) can never clip it — the same freedom native
   * titles have. The final shift is applied through an inline transform so
   * it can nudge clear of the window edges without fighting Tailwind's
   * translate utilities.
   */
  const measure = useCallback(() => {
    const wrapper = wrapperRef.current;
    const bubble = bubbleRef.current;
    if (!wrapper || !bubble) return;

    const rect = wrapper.getBoundingClientRect();
    const size = { w: bubble.offsetWidth, h: bubble.offsetHeight };

    // Flip to the opposite side when the preferred one would hang outside the
    // window; keep the preferred side when neither fits (best available).
    const resolved = fits(placement, rect, size)
      ? placement
      : fits(FLIPPED[placement], rect, size)
        ? FLIPPED[placement]
        : placement;

    const nudgeFor = computeNudge(resolved, rect, size);
    setSide(resolved);
    setNudge(nudgeFor);

    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    if (resolved === "top") {
      setBubblePos({ left: centerX, top: rect.top - OFFSET - size.h });
    } else if (resolved === "bottom") {
      setBubblePos({ left: centerX, top: rect.bottom + OFFSET });
    } else if (resolved === "left") {
      setBubblePos({ left: rect.left - OFFSET - size.w, top: centerY });
    } else {
      setBubblePos({ left: rect.right + OFFSET, top: centerY });
    }
  }, [placement]);

  // Hide whenever the layout scrolls or resizes so an anchor that has moved
  // can't leave a stale bubble stranded. A fresh hover re-measures it.
  useEffect(() => {
    if (!visible) return;
    const outside = () => setVisible(false);
    window.addEventListener("resize", outside);
    window.addEventListener("scroll", outside, true);
    return () => {
      window.removeEventListener("resize", outside);
      window.removeEventListener("scroll", outside, true);
    };
  }, [visible]);

  /**
   * Reveal the bubble. Pointer hovers go through a short hover-intent delay
   * (issue #61); keyboard focus reveals instantly. Suppressed callers never
   * show.
   */
  const show = (immediate: boolean) => {
    if (suppress) return;
    clearHoverTimer();
    const reveal = () => {
      measure();
      setVisible(true);
    };
    if (immediate) {
      reveal();
    } else {
      hoverTimerRef.current = window.setTimeout(reveal, HOVER_DELAY_MS);
    }
  };

  const hide = () => {
    clearHoverTimer();
    setVisible(false);
  };

  // Escape dismisses the bubble (WCAG 1.4.13, issue #61). Capture phase so
  // handlers that stopPropagation on Escape (menus, comboboxes) can't swallow
  // it; we never consume the event, so those handlers still run.
  useEffect(() => {
    if (!visible) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setVisible(false);
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [visible]);

  // The bubble sits above every other layer (z-tooltip), so a dialog mounting
  // while it is up — the trigger's own action opened one — would float over
  // the modal (issue #59). Yield the moment a dialog appears; a fresh hover
  // re-measures once it is gone.
  useEffect(() => {
    if (!visible) return;
    const dialogOpen = () =>
      Boolean(document.querySelector('[role="dialog"][aria-modal="true"], dialog[open]'));
    if (dialogOpen()) {
      setVisible(false);
      return;
    }
    const observer = new MutationObserver(() => {
      if (dialogOpen()) setVisible(false);
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["role", "aria-modal", "open", "class"],
    });
    return () => observer.disconnect();
  }, [visible]);

  /** Attach hover/focus handling plus an accessible reference to the bubble. */
  const triggerProps = {
    onMouseEnter: () => show(false),
    onMouseLeave: hide,
    onFocus: () => show(true),
    onBlur: hide,
    "aria-describedby": tooltipId,
  } as Record<string, unknown>;

  return (
    <div
      ref={wrapperRef}
      className={`group relative ${block ? "flex min-w-0 flex-1 items-center" : "inline-flex shrink-0 items-center"}`}
      onMouseEnter={() => show(false)}
      onMouseLeave={hide}
      onFocus={() => show(true)}
      onBlur={hide}
    >
      {cloneElement(children, triggerProps)}
      {createPortal(
        <span
          ref={bubbleRef}
          id={tooltipId}
          role="tooltip"
          className={`pointer-events-none invisible fixed z-[var(--z-tooltip)] w-max max-w-[calc(100vw-16px)] rounded-md border border-line bg-elevated px-2 py-1 text-left text-[11px] leading-relaxed text-ink shadow-lg ${
            visible ? "visible opacity-100" : "opacity-0"
          }`}
          style={{
            left: bubblePos.left,
            top: bubblePos.top,
            transform:
              side === "top" || side === "bottom"
                ? `translateX(calc(-50% + ${nudge.x}px))`
                : `translateY(calc(-50% + ${nudge.y}px))`,
          }}
        >
          {text}
          <span
            className={`absolute h-2 w-2 rotate-45 border-line bg-elevated ${ARROW_CLASS[side]} ${ARROW_BORDERS[side]}`}
            style={
              side === "top" || side === "bottom" ? { left: `calc(50% - ${nudge.x}px)` } : undefined
            }
          />
        </span>,
        document.body,
      )}
    </div>
  );
};

export default Tooltip;