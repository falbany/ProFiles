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
