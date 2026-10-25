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
          <code key={pIdx} className="rounded bg-elevated px-1 py-0.5 font-mono text-indigo-300">
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

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="workflow-runner-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
    >
      <div className="flex h-[80vh] w-full max-w-4xl flex-col rounded-xl border border-frame-line glass-panel overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5 bg-surface-strong/30 shrink-0">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
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
                        ? "border-indigo-500/60 bg-indigo-500/15 shadow-xs ring-1 ring-indigo-500/30"
                        : "border-line/60 bg-surface/60 hover:bg-elevated/80"
                    }`}
                  >
                    <div className="mt-0.5 shrink-0">
                      {st.status === "running" && (
                        <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                      )}
                      {st.status === "completed" && (
                        <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                      )}
                      {st.status === "skipped" && (
                        <FastForward className="h-4 w-4 text-amber-400" />
                      )}
                      {st.status === "failed" && (
                        <AlertCircle className="h-4 w-4 text-red-400" />
                      )}
                      {st.status === "pending" && (
                        <div className="h-4 w-4 rounded-full border border-line-strong flex items-center justify-center text-[10px] text-ink-faint font-mono">
                          {st.index}
                        </div>
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[11px] font-bold uppercase text-indigo-400">
                          {st.action}
                        </span>
                        <span className="text-[10px] font-mono text-ink-faint">#{st.index}</span>
                      </div>
                      <p className="truncate font-mono text-[11px] text-ink-secondary mt-0.5" title={st.content}>
                        {st.content}
                      </p>
                      {st.message && (
                        <p className="mt-1 text-[10px] text-ink-faint italic">{st.message}</p>
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
                <div className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-400">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              {/* Active / Inspected Step Details */}
              <div className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4">
                <div className="flex items-center justify-between border-b border-line pb-3">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-indigo-500/10 px-2 py-0.5 font-mono text-xs font-semibold uppercase text-indigo-300">
                      {activeStep?.action || session?.status}
                    </span>
                    <span className="text-xs text-ink-muted">
                      {activeStep ? `Step ${activeStep.index} of ${session?.steps.length}` : "Status"}
                    </span>
                    {(selectedStepIndex !== null && selectedStepIndex !== session?.current_index) && (
                      <button
                        type="button"
                        onClick={() => setSelectedStepIndex(null)}
                        className="text-[11px] text-indigo-400 hover:underline ml-2"
                      >
                        (Return to active step)
                      </button>
                    )}
                  </div>
                  {loading && <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />}
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
                    </div>
                  )}

                  {(selectedStepIndex === null || selectedStepIndex === session?.current_index) && session?.status === "waiting_ask" && session.ask_prompt && (
                    <div className="space-y-2">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-amber-400">Confirmation Prompt:</p>
                      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm font-medium text-ink">
                        {session.ask_prompt}
                      </div>
                    </div>
                  )}

                  {/* Priority 2: Full-screen completion banner (only if NO step is specifically being inspected) */}
                  {isFinished && selectedStepIndex === null && (
                    <div className={`rounded-xl border p-8 text-center space-y-4 ${
                      session?.status === "completed"
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                        : "border-red-500/30 bg-red-500/10 text-red-300"
                    }`}>
                      <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-surface/50 mx-auto">
                        {session?.status === "completed" ? (
                          <CheckCircle2 className="h-6 w-6 text-emerald-400" />
                        ) : (
                          <AlertCircle className="h-6 w-6 text-red-400" />
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
                          className="rounded-lg bg-indigo-600 px-8 py-2.5 text-xs font-bold text-white shadow-lg hover:bg-indigo-500 transition-all scale-105 active:scale-95"
                        >
                          Close Engine Runner
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Priority 3: General content display for inspected or non-prompting current step */}
                  {!(isFinished && selectedStepIndex === null) && 
                   !((selectedStepIndex === null || selectedStepIndex === session?.current_index) && (session?.status === "waiting_notify" || session?.status === "waiting_ask")) && (
                    <div className="space-y-4">
                      <div className="space-y-2">
                        <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Step Content:</p>
                        <div className="rounded-lg border border-line bg-surface-strong p-4 font-mono text-xs text-ink leading-relaxed">
                          {activeStep?.content ? renderMarkdown(activeStep.content) : "Waiting..."}
                        </div>
                      </div>
                      
                      {activeStep?.ask && (
                        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-300">
                          <span className="font-semibold">Workflow Guard:</span> {activeStep.ask}
                        </div>
                      )}
                      
                      {activeStep?.message && (
                        <div className="rounded-lg border border-line bg-surface-strong p-3 text-xs text-ink-muted italic">
                          <span className="font-semibold text-ink-secondary not-italic uppercase text-[10px]">Log:</span> {activeStep.message}
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
                  : isFinished
                  ? "Session terminated."
                  : "Step in progress..."}
              </div>

              <div className="flex items-center gap-2">
                {session?.status === "waiting_notify" && (selectedStepIndex === null || selectedStepIndex === session.current_index) && (
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => handleRespond("ack")}
                    className="rounded-md bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline-none"
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
                      className="rounded-md border border-line bg-surface px-4 py-2 text-xs font-medium text-red-400 hover:bg-red-500/10"
                    >
                      Abort Launch
                    </button>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => handleRespond("skip")}
                      className="rounded-md border border-line bg-surface px-4 py-2 text-xs font-medium text-amber-400 hover:bg-amber-500/10"
                    >
                      Skip Step
                    </button>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => handleRespond("yes")}
                      className="rounded-md bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500"
                    >
                      Execute Step
                    </button>
                  </>
                )}

                {isFinished && (
                  <button
                    type="button"
                    onClick={onClose}
                    className="rounded-md bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500"
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
