// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { useRef } from "react";
import { useModalA11y } from "./useModalA11y";

/** Minimal dialog wired through the hook, with an app button "behind" it. */
function Fixture({ onClose }: { onClose: () => void }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const handleDialogKeyDown = useModalA11y({ isOpen: true, onClose, dialogRef });
  return (
    <div>
      <button type="button" id="behind-app">
        behind-app-button
      </button>
      <div ref={dialogRef} role="dialog" aria-modal="true" onKeyDown={handleDialogKeyDown}>
        <button type="button" id="first">
          first
        </button>
        <input id="middle" aria-label="middle" />
        <button type="button" id="last">
          last
        </button>
      </div>
    </div>
  );
}

function pressTab(shift = false): void {
  document.body.dispatchEvent(
    new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true, shiftKey: shift }),
  );
}

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

describe("useModalA11y focus trap", () => {
  it("pulls focus into the dialog when Tab is pressed while focus is on body", () => {
    render(<Fixture onClose={vi.fn()} />);
    screen.getByText("behind-app-button");
    (document.activeElement as HTMLElement | null)?.blur?.();
    expect(document.activeElement).toBe(document.body);

    pressTab();

    // Focus lands on the first control INSIDE the dialog — never on the
    // app behind the modal.
    expect(document.activeElement?.id).toBe("first");
  });

  it("Shift+Tab from body pulls focus to the last control", () => {
    render(<Fixture onClose={vi.fn()} />);
    screen.getByText("behind-app-button");
    (document.activeElement as HTMLElement | null)?.blur?.();

    pressTab(true);

    expect(document.activeElement?.id).toBe("last");
  });

  it("wraps forward from the last focusable back to the first", () => {
    render(<Fixture onClose={vi.fn()} />);
    screen.getByText("behind-app-button");
    (document.getElementById("last") as HTMLElement).focus();

    pressTab();

    expect(document.activeElement?.id).toBe("first");
  });

  it("wraps backward with Shift+Tab from the first focusable", () => {
    render(<Fixture onClose={vi.fn()} />);
    screen.getByText("behind-app-button");
    (document.getElementById("first") as HTMLElement).focus();

    pressTab(true);

    expect(document.activeElement?.id).toBe("last");
  });

  it("keeps focus inside the dialog across repeated Tabs", () => {
    render(<Fixture onClose={vi.fn()} />);
    screen.getByText("behind-app-button");
    (document.activeElement as HTMLElement | null)?.blur?.();

    pressTab();
    pressTab(); // last wrap edge (first → last)
    pressTab();

    const dialog = screen.getByRole("dialog");
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("Escape still closes when focus is inside the dialog", () => {
    const onClose = vi.fn();
    render(<Fixture onClose={onClose} />);
    screen.getByText("behind-app-button");
    (document.getElementById("first") as HTMLElement).focus();

    document.getElementById("first")!.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }),
    );

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
