// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WorkflowRunnerModal } from "./WorkflowRunnerModal";
import {
  abortWorkflowSession,
  respondWorkflowSession,
  startWorkflowSession,
} from "../api/client";
import type { WorkflowSessionState, WorkflowStepRecord } from "../api/types";

vi.mock("../api/client", () => ({
  startWorkflowSession: vi.fn(),
  respondWorkflowSession: vi.fn(),
  abortWorkflowSession: vi.fn(),
}));

const startSpy = vi.mocked(startWorkflowSession);
const respondSpy = vi.mocked(respondWorkflowSession);
const abortSpy = vi.mocked(abortWorkflowSession);

/** Minimal step record; only what the modal reads. */
function step(index: number, status: WorkflowStepRecord["status"] = "completed"): WorkflowStepRecord {
  return {
    index,
    action: "run",
    command: `cmd-${index}`,
    status,
  };
}

function makeSession(overrides: Partial<WorkflowSessionState> = {}): WorkflowSessionState {
  return {
    session_id: "sess-1",
    filename: "build.mttl",
    pattern: "1.0",
    status: "waiting_ask",
    current_index: 1,
    ask_prompt: "Execute this step?",
    steps: [step(0), step(1, "pending")],
    ...overrides,
  };
}

function renderModal(overrides: { onClose?: () => void } = {}) {
  const onClose = vi.fn(overrides.onClose);
  const onFinished = vi.fn();
  render(
    <WorkflowRunnerModal
      isOpen
      onClose={onClose}
      directory="C:/d"
      filename="build.mttl"
      release="1.0"
      onFinished={onFinished}
    />,
  );
  return { onClose, onFinished };
}

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

beforeEach(() => {
  vi.clearAllMocks();
  startSpy.mockResolvedValue(makeSession());
  respondSpy.mockResolvedValue(makeSession({ status: "completed", current_index: 2 }));
  abortSpy.mockResolvedValue(undefined as never);
});

describe("Escape key routing (#83)", () => {
  it("closes exactly once per press when focus is inside the dialog", async () => {
    const user = userEvent.setup();
    const { onClose } = renderModal();

    // Focus a step button so the keydown bubbles through the dialog too.
    await waitFor(() => screen.getByText(/Workflow Steps/i));
    await waitFor(() => expect(startSpy).toHaveBeenCalled());
    await waitFor(() => screen.findByRole("dialog"));

    const stepButton = await screen
      .findAllByRole("button")
      .then((buttons) => buttons.find((b) => b.textContent?.includes("#0")));
    expect(stepButton).toBeDefined();
    await user.click(stepButton as HTMLElement);
    await user.keyboard("{Escape}");

    await waitFor(() => {
      expect(abortSpy).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  it("closes exactly once per press when focus is outside the dialog", async () => {
    const { onClose } = renderModal();

    // Session fully loaded: the interactive controls are rendered.
    await screen.findByRole("button", { name: "Execute Step" });

    // Nothing focusable: activeElement is body, keydown cannot bubble
    // through the dialog element. Dispatch from the body to prove the
    // window-level listener closes the modal regardless of focus location.
    (document.activeElement as HTMLElement | null)?.blur?.();
    document.body.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }),
    );

    await waitFor(() => {
      expect(abortSpy).toHaveBeenCalledTimes(1);
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });
});

describe("initial focus (#81)", () => {
  it("focuses the primary action button, not the close X, on waiting_ask open", async () => {
    renderModal();
    const primary = await screen.findByRole("button", { name: "Execute Step" });
    await waitFor(() => expect(document.activeElement).toBe(primary));
  });

  it("moves focus to the new primary action when the session terminates", async () => {
    const user = userEvent.setup();
    renderModal();

    const primary = await screen.findByRole("button", { name: "Execute Step" });
    await waitFor(() => expect(document.activeElement).toBe(primary));

    await user.click(primary);
    const closeRunner = await screen.findByRole("button", { name: "Close Runner" });
    await waitFor(() => expect(document.activeElement).toBe(closeRunner));
  });
});

describe("bypass button", () => {
  it("sends the bypass action from the header on a pre-phase ask gate", async () => {
    const user = userEvent.setup();
    renderModal();
    const bypass = await screen.findByRole("button", { name: /launch now/i });
    await user.click(bypass);
    await waitFor(() => expect(respondSpy).toHaveBeenCalledWith("sess-1", "bypass"));
  });

  it("labels the action Skip rest on a post-phase gate", async () => {
    startSpy.mockResolvedValue(
      makeSession({
        status: "waiting_notify",
        current_index: 1,
        notify_message: "Launched!",
        steps: [step(0), { ...step(1, "pending"), phase: "post" }],
      }),
    );
    renderModal();
    const bypass = await screen.findByRole("button", { name: /skip rest/i });
    expect((bypass as HTMLButtonElement).disabled).toBe(false);
  });

  it("is disabled while a step is running", async () => {
    startSpy.mockResolvedValue(makeSession({ status: "running" }));
    renderModal();
    const bypass = await screen.findByRole("button", { name: /launch now/i });
    expect((bypass as HTMLButtonElement).disabled).toBe(true);
  });

  it("is hidden once the session is terminal", async () => {
    startSpy.mockResolvedValue(makeSession({ status: "completed", current_index: 2 }));
    renderModal();
    await screen.findByRole("button", { name: "Close Runner" });
    expect(screen.queryByRole("button", { name: /launch now/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /skip rest/i })).toBeNull();
  });
});

describe("gate keyboard shortcuts", () => {
  async function renderAskGate() {
    renderModal();
    await screen.findByRole("button", { name: "Execute Step" });
  }

  function press(key: string, modifiers: KeyboardEventInit = {}): void {
    document.body.dispatchEvent(
      new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true, ...modifiers }),
    );
  }

  it("Y answers yes on an ask gate", async () => {
    await renderAskGate();
    press("y");
    await waitFor(() => expect(respondSpy).toHaveBeenLastCalledWith("sess-1", "yes"));
  });

  it("S skips the step on an ask gate", async () => {
    await renderAskGate();
    press("s");
    await waitFor(() => expect(respondSpy).toHaveBeenLastCalledWith("sess-1", "skip"));
  });

  it("N aborts the launch on an ask gate", async () => {
    await renderAskGate();
    press("n");
    await waitFor(() => expect(respondSpy).toHaveBeenLastCalledWith("sess-1", "no"));
  });

  it("Enter confirms the gate when focus is not on a button", async () => {
    await renderAskGate();
    (document.activeElement as HTMLElement | null)?.blur?.();
    press("Enter");
    await waitFor(() => expect(respondSpy).toHaveBeenLastCalledWith("sess-1", "yes"));
  });

  it("Enter does nothing while a button holds focus (native activation rules)", async () => {
    await renderAskGate();
    screen.getByRole("button", { name: "Abort Launch" }).focus();
    press("Enter");
    expect(respondSpy).not.toHaveBeenCalled();
  });

  it("ignores modifier combos", async () => {
    await renderAskGate();
    press("y", { ctrlKey: true });
    press("n", { metaKey: true });
    expect(respondSpy).not.toHaveBeenCalled();
  });

  it("ignores keys while inspecting another step", async () => {
    const user = userEvent.setup();
    await renderAskGate();
    await user.click(screen.getByRole("button", { name: /#0/ }));
    press("y");
    press("Enter");
    expect(respondSpy).not.toHaveBeenCalled();
  });
});

describe("gate key hints", () => {
  it("shows Y / S / N hints on the ask buttons without changing their names", async () => {
    renderModal();
    const execute = await screen.findByRole("button", { name: "Execute Step" });
    expect(execute.textContent).toContain("Y");
    expect(screen.getByRole("button", { name: "Abort Launch" }).textContent).toContain("N");
    expect(screen.getByRole("button", { name: "Skip Step" }).textContent).toContain("S");
  });

  it("hints Enter on the ack buttons", async () => {
    startSpy.mockResolvedValue(
      makeSession({ status: "waiting_notify", current_index: 0, notify_message: "Notice" }),
    );
    renderModal();
    const ack = await screen.findByRole("button", { name: "Continue Workflow" });
    expect(ack.textContent).toContain("↵");
    expect(ack.querySelector("kbd")).toBeTruthy();
  });
});

describe("copy buttons (#78)", () => {
  function mockClipboard(): ReturnType<typeof vi.fn> {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });
    return writeText;
  }

  it("copies the interactive command text and flips to Copied", async () => {
    // userEvent.setup() patches navigator.clipboard with its own stub:
    // install our mock AFTER setup or it is silently replaced (#78 tests).
    const user = userEvent.setup();
    const writeText = mockClipboard();
    renderModal();
    const copy = await screen.findByRole("button", { name: "Copy content" });
    await user.click(copy);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("cmd-1"));
    expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy();
  });

  it("copies the finished-session command output", async () => {
    const user = userEvent.setup();
    const writeText = mockClipboard();
    startSpy.mockResolvedValue(
      makeSession({ status: "completed", current_index: 2, last_output: "out-line" }),
    );
    renderModal();
    const copy = await screen.findByRole("button", { name: "Copy content" });
    await user.click(copy);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("out-line"));
  });

  it("swallows clipboard failures silently (webview without clipboard API)", async () => {
    const user = userEvent.setup();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockRejectedValue(new Error("nope")) },
      configurable: true,
    });
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    renderModal();
    const copy = await screen.findByRole("button", { name: "Copy content" });
    await user.click(copy);
    // Still labelled Copy: the copy did not happen, and no error UI appears.
    expect(await screen.findByRole("button", { name: "Copy content" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Copied" })).toBeNull();
    consoleSpy.mockRestore();
  });
});

describe("session-expired recovery (#79)", () => {
  function goneError(): Error {
    return Object.assign(new Error("Session not found"), { status: 404 });
  }

  it("switches to the recovery panel when respond 404s", async () => {
    const user = userEvent.setup();
    respondSpy.mockRejectedValue(goneError());
    renderModal();
    const exec = await screen.findByRole("button", { name: "Execute Step" });
    await user.click(exec);

    expect(await screen.findByText(/has expired or ended/i)).toBeTruthy();
    // Dead footer gates are replaced by recovery actions.
    expect(screen.queryByRole("button", { name: "Execute Step" })).toBeNull();
    expect(screen.queryByRole("button", { name: /launch now/i })).toBeNull();
    expect(screen.getByRole("button", { name: /restart workflow/i })).toBeTruthy();
    // Raw error kept for diagnostics behind the collapsible.
    expect(screen.getByText(/Raw error/i)).toBeTruthy();
    // Sidebar shows the explicit unavailable state.
    expect(screen.getByText(/Session unavailable/i)).toBeTruthy();
    expect(screen.queryByText(/Loading steps/i)).toBeNull();
  });

  it("restart re-issues start with identical props and clears the error", async () => {
    const user = userEvent.setup();
    respondSpy.mockRejectedValueOnce(goneError());
    renderModal();
    const exec = await screen.findByRole("button", { name: "Execute Step" });
    await user.click(exec);
    await screen.findByText(/has expired or ended/i);

    await user.click(screen.getByRole("button", { name: /restart workflow/i }));
    await waitFor(() => expect(startSpy).toHaveBeenCalledTimes(2));
    expect(startSpy).toHaveBeenLastCalledWith({
      directory: "C:/d",
      filename: "build.mttl",
      release: "1.0",
      args: undefined,
    });
    // The session is interactive again and the error strip is gone.
    await screen.findByRole("button", { name: "Execute Step" });
    expect(screen.queryByText(/has expired or ended/i)).toBeNull();
  });

  it("non-404 respond errors keep the gates and show the pinned banner", async () => {
    const user = userEvent.setup();
    respondSpy.mockRejectedValueOnce(new Error("boom"));
    renderModal();
    const exec = await screen.findByRole("button", { name: "Execute Step" });
    await user.click(exec);
    expect(await screen.findByText("boom")).toBeTruthy();
    // Not a session-gone error: gates stay available.
    expect(screen.getByRole("button", { name: "Execute Step" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /restart workflow/i })).toBeNull();
  });

  it("start failure shows the pinned banner and an explicit sidebar state", async () => {
    startSpy.mockRejectedValue(
      Object.assign(new Error("No matching workflow found for file"), { status: 400 }),
    );
    renderModal();
    expect(await screen.findByText(/No matching workflow/i)).toBeTruthy();
    expect(screen.getByText(/Session unavailable/i)).toBeTruthy();
    expect(screen.queryByText(/Loading steps/i)).toBeNull();
  });
});

describe("step sidebar semantics (#80)", () => {
  it("renders a semantic list with visible status words and aria-current", async () => {
    renderModal();
    const step1 = await screen.findByRole("button", { name: /#1/ });
    expect(screen.getByRole("list")).toBeTruthy();
    // Status is text, not color-only (WCAG 1.4.1): current step is pending.
    expect(step1.textContent).toContain("pending");
    expect(screen.getByRole("button", { name: /#0/ }).textContent).toContain("done");
    expect(step1.getAttribute("aria-current")).toBe("step");
    expect(screen.getByRole("button", { name: /#0/ }).getAttribute("aria-current")).toBeNull();
  });

  it("uses a roving tabindex and moves selection with arrow keys", async () => {
    renderModal();
    const step0 = await screen.findByRole("button", { name: /#0/ });
    const step1 = screen.getByRole("button", { name: /#1/ });
    // Single Tab stop: only the inspected row is tabbable.
    expect(step0.getAttribute("tabindex")).toBe("-1");
    expect(step1.getAttribute("tabindex")).toBe("0");

    step1.focus();
    step1.dispatchEvent(
      new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true, cancelable: true }),
    );
    await waitFor(() => {
      const nowCurrent = screen.getByRole("button", { name: /#0/ });
      expect(nowCurrent.getAttribute("aria-current")).toBe("step");
      expect(document.activeElement).toBe(nowCurrent);
    });
  });

  it("footer status hint is a live region", async () => {
    renderModal();
    const hint = await screen.findByText(/Action required to proceed/i);
    expect(hint.getAttribute("aria-live")).toBe("polite");
  });
});

describe("keyboard guard residuals (#82)", () => {
  it("Enter closes the runner when finished and no button holds focus", async () => {
    const { onClose } = renderModal();
    const user = userEvent.setup();
    respondSpy.mockResolvedValue(makeSession({ status: "completed", current_index: 2 }));
    await user.click(await screen.findByRole("button", { name: "Execute Step" }));
    await screen.findByRole("button", { name: "Close Runner" });
    (document.activeElement as HTMLElement | null)?.blur?.();
    document.body.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }),
    );
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
  });

  it("gate keys are ignored while focus is in a text input", async () => {
    renderModal();
    await screen.findByRole("button", { name: "Execute Step" });
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    input.dispatchEvent(
      new KeyboardEvent("keydown", { key: "y", bubbles: true, cancelable: true }),
    );
    expect(respondSpy).not.toHaveBeenCalled();
    input.remove();
  });
});
