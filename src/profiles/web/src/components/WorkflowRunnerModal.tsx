import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FastForward,
  Loader2,
  Webhook,
  X,
} from "lucide-react";
import {
  respondWorkflowSession,
  startWorkflowSession,
} from "../api/client";
import type { WorkflowSessionState, WorkflowStepRecord } from "../api/types";

interface WorkflowRunnerModalProps {
  isOpen: boolean;
  onClose: () => void;
  directory: string;
  filename: string;
  release?: string;
  args?: string;
  onFinished?: (status: string, message: string) => void;
}

/** Simple parser for Markdown subset (# heading, **bold**, *italic*, `code`, \n) */
function renderMarkdown(text: string) {
  if (!text) return null;
  const unescaped = text
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, "\\");

  const lines = unescaped.split("\n");
  return lines.map((line, lIdx) => {
    let content = line;
    let type: "h1" | "h2" | "p" = "p";

    if (line.startsWith("# ")) {
      type = "h1";
      content = line.slice(2);
    } else if (line.startsWith("## ")) {
      type = "h2";
      content = line.slice(3);
    }

    const parts = content.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`)/g);

    const renderedInline = parts.map((part, pIdx) => {
      if (!part) return null;
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
        return (
          <strong key={pIdx} className="font-semibold text-ink">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
        return (
          <em key={pIdx} className="italic text-ink-secondary">
            {part.slice(1, -1)}
          </em>
        );
      }
      if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
        return (
          <code key={pIdx} className="rounded bg-elevated px-1 py-0.5 font-mono text-chip-indigo-text">
            {part.slice(1, -1)}
          </code>
        );
      }
      return <span key={pIdx}>{part}</span>;
    });

    if (type === "h1") {
      return (
        <h3 key={lIdx} className="text-base font-bold text-ink">
          {renderedInline}
        </h3>
      );
    }
    if (type === "h2") {
      return (
        <h4 key={lIdx} className="text-sm font-semibold text-ink">
          {renderedInline}
        </h4>
      );
    }
    return (
      <p key={lIdx} className="min-h-[1rem]">
        {renderedInline}
      </p>
    );
  });
}

export function WorkflowRunnerModal({
  isOpen,
  onClose,
  directory,
  filename,
  release,
  args,
  onFinished,
}: WorkflowRunnerModalProps) {
  const [session, setSession] = useState<WorkflowSessionState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedStepIndex, setSelectedStepIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!isOpen || !directory || !filename) {
      setSession(null);
      setError(null);
      setSelectedStepIndex(null);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);
    setSelectedStepIndex(null);

    startWorkflowSession({
      directory,
      filename,
      release,
      args,
    })
      .then((s) => {
        if (!active) return;
        setSession(s);
        setLoading(false);
        if (s.status === "completed" || s.status === "aborted" || s.status === "failed") {
          onFinished?.(s.status, s.final_message || "");
        }
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Failed to start workflow");
        setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [isOpen, directory, filename, release, args]);

  const handleRespond = async (action: "yes" | "skip" | "no" | "ack") => {
    if (!session) return;
    setLoading(true);
    try {
      const next = await respondWorkflowSession(session.session_id, action);
      setSession(next);
      if (next.status === "completed" || next.status === "aborted" || next.status === "failed") {
        onFinished?.(next.status, next.final_message || "");
      }
    } catch (err: any) {
      setError(err.message || "Failed to process workflow response");
    } finally {
      setLoading(false);
    }
  };

  // Close on Escape key press
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const activeStep: WorkflowStepRecord | undefined =
    selectedStepIndex !== null
      ? session?.steps[selectedStepIndex]
      : session?.steps[session.current_index];

  const isFinished =
    session?.status === "completed" || session?.status === "aborted" || session?.status === "failed";

  // Command box for the interactive (waiting_*) panels: the generic detail
  // panel below is suppressed while the session waits on the current step,
  // so the command must be surfaced here as well — after the human-readable
  // message, per the message-first ordering.
  const showInteractivePanels =
    selectedStepIndex === null || selectedStepIndex === session?.current_index;
  const interactiveCommandBox =
    showInteractivePanels &&
    activeStep?.command &&
    (session?.status === "waiting_notify" ||
      session?.status === "waiting_notice" ||
      session?.status === "waiting_ask") ? (
      <div className="space-y-2">
        <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Command:</p>
        <div className="rounded-lg border border-line bg-surface-strong p-4 font-mono text-xs text-ink leading-relaxed">
          {activeStep.command}
        </div>
      </div>
    ) : null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="workflow-runner-title"
      className="animate-overlay-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
    >
      <div className="animate-modal-in flex h-[80vh] w-full max-w-4xl flex-col rounded-xl border border-frame-line glass-panel overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5 bg-surface-strong/30 shrink-0">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-chip-indigo-bg text-chip-indigo-text">
              <Webhook className="h-4 w-4" />
            </span>
            <div>
              <h2 id="workflow-runner-title" className="text-sm font-semibold text-ink">
                Launch Workflow Engine
              </h2>
              <p className="text-xs text-ink-muted">
                {filename} {session?.pattern ? `• Pattern: ${session.pattern}` : ""}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-ink-muted hover:bg-elevated hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Main Split Layout: Left Sidebar (Steps) + Right Content */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Sidebar: Steps */}
          <div className="w-80 border-r border-line bg-surface-strong/20 p-4 overflow-y-auto flex flex-col gap-2 shrink-0">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-ink-muted px-1 mb-1">
              Workflow Steps (Click to inspect)
            </h3>
            {session && session.steps.length > 0 ? (
              session.steps.map((st, idx) => {
                const isCurrentExecuting = session.current_index === idx && !isFinished;
                const isInspected = selectedStepIndex === idx || (selectedStepIndex === null && isCurrentExecuting);
                return (
                  <button
                    key={st.index}
                    type="button"
                    onClick={() => setSelectedStepIndex(idx)}
                    className={`flex items-start text-left gap-2.5 rounded-lg border px-3 py-2.5 transition-colors cursor-pointer w-full ${
                      isInspected
                        ? "border-chip-indigo-border bg-chip-indigo-bg shadow-xs ring-1 ring-chip-indigo-border/40"
                        : "border-line/60 bg-surface/60 hover:bg-elevated/80"
                    }`}
                  >
                    <div className="mt-0.5 shrink-0">
                      {st.status === "running" && (
                        <Loader2 className="h-4 w-4 animate-spin text-chip-indigo-text" />
                      )}
                      {st.status === "completed" && (
                        <CheckCircle2 className="h-4 w-4 text-status-success-text" />
                      )}
                      {st.status === "skipped" && (
                        <FastForward className="h-4 w-4 text-status-warning-text" />
                      )}
                      {st.status === "failed" && (
                        <AlertCircle className="h-4 w-4 text-status-danger-text" />
                      )}
                      {st.status === "pending" && (
                        <div className="h-4 w-4 rounded-full border border-line-strong flex items-center justify-center text-[10px] text-ink-faint font-mono">
                          {st.index}
                        </div>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[11px] font-bold uppercase text-chip-indigo-text">
                          {st.action}
                        </span>
                        <span className="text-[10px] font-mono text-ink-faint">#{st.index}</span>
                      </div>
                      <p
                        className="truncate font-mono text-[11px] text-ink-secondary mt-0.5"
                        title={st.command}
                      >
                        {st.message ? st.message.split("\n")[0] : st.command}
                      </p>
                      {st.note && (
                        <p className="mt-1 text-[10px] text-ink-faint italic">{st.note}</p>
                      )}
                    </div>
                  </button>
                );
              })
            ) : (
              <div className="p-4 text-center text-xs text-ink-faint">Loading steps...</div>
            )}
          </div>

          {/* Right Content Area */}
          <div className="flex-1 flex flex-col bg-app overflow-y-auto p-6 justify-between">
            <div className="space-y-6">
              {error && (
                <div className="flex items-start gap-2 rounded-lg border border-status-danger-border bg-status-danger-bg p-3 text-xs text-status-danger-text">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {/* Active / Inspected Step Details */}
              <div className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4">
                <div className="flex items-center justify-between border-b border-line pb-3">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-chip-indigo-bg px-2 py-0.5 font-mono text-xs font-semibold uppercase text-chip-indigo-text">
                      {activeStep?.action || session?.status}
                    </span>
                    <span className="text-xs text-ink-muted">
                      {activeStep ? `Step ${activeStep.index} of ${session?.steps.length}` : "Status"}
                    </span>
                    {(selectedStepIndex !== null && selectedStepIndex !== session?.current_index) && (
                      <button
                        type="button"
                        onClick={() => setSelectedStepIndex(null)}
                        className="text-[11px] text-chip-indigo-text hover:underline ml-2"
                      >
                        (Return to active step)
                      </button>
                    )}
                  </div>
                  {loading && <Loader2 className="h-4 w-4 animate-spin text-chip-indigo-text" />}
                </div>

                {/* Content Body / Rendered Markdown */}
                <div className="space-y-3 text-xs text-ink font-sans leading-relaxed">
                  {/* Priority 1: Interactive Prompts (only if on CURRENT executing step) */}
                  {(selectedStepIndex === null || selectedStepIndex === session?.current_index) && session?.status === "waiting_notify" && session.notify_message && (
                    <div className="space-y-2">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Notification Message:</p>
                      <div className="rounded-lg border border-line bg-surface-strong p-4 font-mono text-ink space-y-2">
                        {renderMarkdown(session.notify_message)}
                      </div>
                      {interactiveCommandBox}
                    </div>
                  )}

                  {(selectedStepIndex === null || selectedStepIndex === session?.current_index) && session?.status === "waiting_notice" && session.notice_message && (
                    <div className="space-y-2">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Notice:</p>
                      <div className="rounded-lg border border-line bg-surface-strong p-4 font-mono text-ink space-y-2">
                        {renderMarkdown(session.notice_message)}
                      </div>
                      {interactiveCommandBox}
                      <p className="text-[11px] text-ink-faint">The command will run when you continue.</p>
                    </div>
                  )}

                  {(selectedStepIndex === null || selectedStepIndex === session?.current_index) && session?.status === "waiting_ask" && session.ask_prompt && (
                    <div className="space-y-2">
                      {session.ask_message && (
                        <div className="rounded-lg border border-line bg-surface-strong p-4 font-mono text-ink space-y-2">
                          {renderMarkdown(session.ask_message)}
                        </div>
                      )}
                      <p className="text-[11px] font-medium uppercase tracking-wider text-status-warning-text">Confirmation Prompt:</p>
                      <div className="rounded-lg border border-status-warning-border bg-status-warning-bg p-4 text-sm font-medium text-ink">
                        {session.ask_prompt}
                      </div>
                      {interactiveCommandBox}
                    </div>
                  )}

                  {/* Priority 2: Full-screen completion banner (only if NO step is specifically being inspected) */}
                  {isFinished && selectedStepIndex === null && (
                    <div className={`rounded-xl border p-8 text-center space-y-4 ${
                      session?.status === "completed"
                        ? "border-status-success-border bg-status-success-bg text-status-success-text"
                        : "border-status-danger-border bg-status-danger-bg text-status-danger-text"
                    }`}>
                      <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-surface/50 mx-auto">
                        {session?.status === "completed" ? (
                          <CheckCircle2 className="h-6 w-6 text-status-success-text" />
                        ) : (
                          <AlertCircle className="h-6 w-6 text-status-danger-text" />
                        )}
                      </div>
                      <div className="space-y-1">
                        <h3 className="text-base font-bold">
                          {session?.status === "completed" ? "Workflow Finished" : "Workflow Terminated"}
                        </h3>
                        <p className="text-xs text-ink-secondary max-w-md mx-auto">
                          {session?.final_message || "The launch sequence has ended."}
                        </p>
                      </div>
                      <div className="pt-2">
                        <button
                          type="button"
                          onClick={onClose}
                          className="btn btn-primary px-8 py-2.5 font-bold shadow-lg"
                        >
                          Close Engine Runner
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Command output of the last executed step, below the banner */}
                  {isFinished && selectedStepIndex === null && session?.last_output && (
                    <div className="space-y-2">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">
                        Command Output:
                      </p>
                      <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-surface-strong p-4 font-mono text-xs text-ink">
                        {session.last_output}
                      </pre>
                    </div>
                  )}

                  {/* Priority 3: General content display for inspected or non-prompting current step */}
                  {!(isFinished && selectedStepIndex === null) &&
                   !((selectedStepIndex === null || selectedStepIndex === session?.current_index) && (session?.status === "waiting_notify" || session?.status === "waiting_ask" || session?.status === "waiting_notice")) && (
                    <div className="space-y-4">
                      {activeStep?.message && (
                        <div className="space-y-2">
                          <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Message:</p>
                          <div className="rounded-lg border border-line bg-surface-strong p-4 text-xs text-ink leading-relaxed space-y-2">
                            {renderMarkdown(activeStep.message)}
                          </div>
                        </div>
                      )}

                      <div className="space-y-2">
                        <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Command:</p>
                        <div className="rounded-lg border border-line bg-surface-strong p-4 font-mono text-xs text-ink leading-relaxed">
                          {activeStep?.command ? activeStep.command : "Waiting..."}
                        </div>
                      </div>

                      {activeStep?.output && (
                        <div className="space-y-2">
                          <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Output:</p>
                          <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-surface-strong p-4 font-mono text-xs text-ink">
                            {activeStep.output}
                          </pre>
                        </div>
                      )}

                      {activeStep?.ask && (
                        <div className="rounded-lg border border-status-warning-border bg-status-warning-bg p-3 text-xs text-status-warning-text">
                          <span className="font-semibold">Workflow Guard:</span> {activeStep.ask}
                        </div>
                      )}

                      {activeStep?.note && (
                        <div className="rounded-lg border border-line bg-surface-strong p-3 text-xs text-ink-muted italic">
                          <span className="font-semibold text-ink-secondary not-italic uppercase text-[10px]">Log:</span> {activeStep.note}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Bottom Action Area (Ask Callbacks / Dismiss) */}
            <div className="pt-4 border-t border-line flex items-center justify-between mt-6">
              <div className="text-xs text-ink-muted">
                {session?.status === "waiting_ask" && (selectedStepIndex === null || selectedStepIndex === session.current_index)
                  ? "Action required to proceed:"
                  : session?.status === "waiting_notify" && (selectedStepIndex === null || selectedStepIndex === session.current_index)
                  ? "Acknowledge message to proceed:"
                  : session?.status === "waiting_notice" && (selectedStepIndex === null || selectedStepIndex === session.current_index)
                  ? "Continue to run the command:"
                  : isFinished
                  ? "Session terminated."
                  : "Step in progress..."}
              </div>

              <div className="flex items-center gap-2">
                {session?.status === "waiting_notice" && (selectedStepIndex === null || selectedStepIndex === session.current_index) && (
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => handleRespond("ack")}
                    className="btn btn-primary px-5 py-2 font-semibold shadow-sm"
                  >
                    Run Command
                  </button>
                )}

                {session?.status === "waiting_notify" && (selectedStepIndex === null || selectedStepIndex === session.current_index) && (
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => handleRespond("ack")}
                    className="btn btn-primary px-5 py-2 font-semibold shadow-sm"
                  >
                    Continue Workflow
                  </button>
                )}

                {session?.status === "waiting_ask" && (selectedStepIndex === null || selectedStepIndex === session.current_index) && (
                  <>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => handleRespond("no")}
                      className="btn rounded-md border-line bg-surface px-4 py-2 text-status-danger-text hover:bg-status-danger-bg"
                    >
                      Abort Launch
                    </button>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => handleRespond("skip")}
                      className="btn rounded-md border-line bg-surface px-4 py-2 text-status-warning-text hover:bg-status-warning-bg"
                    >
                      Skip Step
                    </button>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => handleRespond("yes")}
                      className="btn btn-primary px-5 py-2 font-semibold shadow-sm"
                    >
                      Execute Step
                    </button>
                  </>
                )}

                {isFinished && (
                  <button
                    type="button"
                    onClick={onClose}
                    className="btn btn-primary px-5 py-2 font-semibold shadow-sm"
                  >
                    Close Runner
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
