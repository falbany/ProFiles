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
import type { WorkflowSessionState } from "../api/types";

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

  useEffect(() => {
    if (!isOpen || !directory || !filename) {
      setSession(null);
      setError(null);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);

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
  }, [isOpen, directory, filename, release, args, onFinished]);

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

  if (!isOpen) return null;

  const currentStep = session?.steps[session.current_index];
  const isFinished = session?.status === "completed" || session?.status === "aborted" || session?.status === "failed";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="workflow-runner-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
    >
      <div className="flex h-[80vh] w-full max-w-4xl flex-col rounded-xl border border-line bg-surface shadow-2xl overflow-hidden">
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
              Workflow Steps
            </h3>
            {session && session.steps.length > 0 ? (
              session.steps.map((st) => {
                const isCurrent = session.current_index === st.index - 1 && !isFinished;
                return (
                  <div
                    key={st.index}
                    className={`flex items-start gap-2.5 rounded-lg border px-3 py-2.5 transition-colors ${
                      isCurrent
                        ? "border-indigo-500/60 bg-indigo-500/10 shadow-xs"
                        : "border-line/60 bg-surface/60"
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
                  </div>
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

              {/* Active Step Details / Markdown Preview */}
              <div className="rounded-xl border border-line bg-surface p-5 shadow-xs space-y-4">
                <div className="flex items-center justify-between border-b border-line pb-3">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-indigo-500/10 px-2 py-0.5 font-mono text-xs font-semibold uppercase text-indigo-300">
                      {currentStep?.action || session?.status}
                    </span>
                    <span className="text-xs text-ink-muted">
                      {currentStep ? `Step ${currentStep.index} of ${session?.steps.length}` : "Status"}
                    </span>
                  </div>
                  {loading && <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />}
                </div>

                {/* Content Body / Rendered Markdown */}
                <div className="space-y-3 text-xs text-ink font-sans leading-relaxed">
                  {session?.status === "waiting_notify" && session.notify_message ? (
                    <div className="space-y-2">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Notification Message:</p>
                      <div className="rounded-lg border border-line bg-surface-strong p-4 font-mono text-ink space-y-2">
                        {renderMarkdown(session.notify_message)}
                      </div>
                    </div>
                  ) : session?.status === "waiting_ask" && session.ask_prompt ? (
                    <div className="space-y-2">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-amber-400">Confirmation Prompt:</p>
                      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm font-medium text-ink">
                        {session.ask_prompt}
                      </div>
                    </div>
                  ) : session?.status === "completed" ? (
                    <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center space-y-3">
                      <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 mx-auto">
                        <CheckCircle2 className="h-6 w-6" />
                      </div>
                      <h3 className="text-sm font-bold text-emerald-300">Workflow Completed Successfully</h3>
                      <p className="text-xs text-ink-secondary">{session.final_message || "All steps executed successfully. File launched."}</p>
                      <div className="pt-2">
                        <button
                          type="button"
                          onClick={onClose}
                          className="rounded-lg bg-emerald-600 px-6 py-2 text-xs font-bold text-white shadow-sm hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 focus:ring-offset-2 focus:ring-offset-surface transition-all"
                        >
                          Close Workflow
                        </button>
                      </div>
                    </div>
                  ) : session?.status === "aborted" || session?.status === "failed" ? (
                    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-6 text-center space-y-3">
                      <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-red-500/20 text-red-400 mx-auto">
                        <AlertCircle className="h-6 w-6" />
                      </div>
                      <h3 className="text-sm font-bold text-red-300">Workflow Terminated</h3>
                      <p className="text-xs text-ink-secondary">{session.final_message || "Workflow stopped due to user abort or error."}</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">Current Command / Content:</p>
                      <div className="rounded-lg border border-line bg-surface-strong p-3 font-mono text-xs text-ink">
                        {currentStep?.content ? renderMarkdown(currentStep.content) : "Executing steps..."}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Bottom Action Area (Ask Callbacks / Dismiss) */}
            <div className="pt-4 border-t border-line flex items-center justify-between mt-6">
              <div className="text-xs text-ink-muted">
                {session?.status === "waiting_ask"
                  ? "Choose an option below to proceed:"
                  : session?.status === "waiting_notify"
                  ? "Click Continue to acknowledge notification:"
                  : isFinished
                  ? "Workflow session finished."
                  : "Executing workflow steps..."}
              </div>

              <div className="flex items-center gap-2">
                {session?.status === "waiting_notify" && (
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => handleRespond("ack")}
                    className="rounded-md bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                  >
                    Continue
                  </button>
                )}

                {session?.status === "waiting_ask" && (
                  <>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => handleRespond("no")}
                      className="rounded-md border border-line bg-surface px-4 py-2 text-xs font-medium text-red-400 hover:bg-red-500/10 hover:text-red-300"
                    >
                      No (Abort)
                    </button>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => handleRespond("skip")}
                      className="rounded-md border border-line bg-surface px-4 py-2 text-xs font-medium text-amber-400 hover:bg-amber-500/10 hover:text-amber-300"
                    >
                      Skip Step
                    </button>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => handleRespond("yes")}
                      className="rounded-md bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500"
                    >
                      Yes (Execute)
                    </button>
                  </>
                )}

                {isFinished && (
                  <button
                    type="button"
                    onClick={onClose}
                    className="rounded-md bg-indigo-600 px-5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-500"
                  >
                    Close Window
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
