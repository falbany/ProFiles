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
