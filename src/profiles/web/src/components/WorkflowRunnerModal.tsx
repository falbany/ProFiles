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

  // Initialize and start workflow
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

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="workflow-runner-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs"
    >
      <div className="flex max-h-[85vh] w-full max-w-xl flex-col rounded-xl border border-line bg-surface shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400">
              <Webhook className="h-4 w-4" />
            </span>
            <div>
              <h2 id="workflow-runner-title" className="text-sm font-semibold text-ink">
                Launch Workflow
              </h2>
              <p className="text-xs text-ink-muted">
                {filename} {session?.pattern ? `(${session.pattern})` : ""}
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

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 text-xs">
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Steps Checklist */}
          {session && session.steps.length > 0 && (
            <div className="rounded-lg border border-line bg-surface-strong/40 p-3">
              <h3 className="mb-2 font-medium text-ink-secondary">Workflow Steps</h3>
              <div className="space-y-2">
                {session.steps.map((st) => (
                  <div
                    key={st.index}
                    className="flex items-start justify-between gap-3 rounded-md border border-line/60 bg-surface px-3 py-2"
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      <div className="mt-0.5">
                        {st.status === "running" && (
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />
                        )}
                        {st.status === "completed" && (
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                        )}
                        {st.status === "skipped" && (
                          <FastForward className="h-3.5 w-3.5 text-amber-400" />
                        )}
                        {st.status === "failed" && (
                          <AlertCircle className="h-3.5 w-3.5 text-red-400" />
                        )}
                        {st.status === "pending" && (
                          <div className="h-3.5 w-3.5 rounded-full border border-line-strong" />
                        )}
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5 font-mono text-[11px] text-ink font-semibold">
                          <span className="text-ink-muted">#{st.index}</span>
                          <span className="uppercase text-indigo-400/90">{st.action}</span>
                        </div>
                        <p className="truncate font-mono text-[11px] text-ink-secondary" title={st.content}>
                          {st.content}
                        </p>
                        {st.message && (
                          <p className="mt-0.5 text-[10px] text-ink-faint italic">{st.message}</p>
                        )}
                      </div>
                    </div>
                    {st.ask && (
                      <span className="shrink-0 rounded bg-indigo-500/10 px-1.5 py-0.5 text-[10px] text-indigo-300">
                        Guarded (ask)
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Interactive Prompts Area */}
          {session?.status === "waiting_notify" && (
            <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-4 space-y-3">
              <h4 className="font-semibold text-indigo-300">Notification</h4>
              <div className="whitespace-pre-wrap rounded bg-surface/80 p-3 font-mono text-ink border border-line">
                {session.notify_message}
              </div>
              <div className="flex justify-end">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => handleRespond("ack")}
                  className="rounded-md bg-indigo-600 px-4 py-1.5 font-medium text-white hover:bg-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
                >
                  Continue
                </button>
              </div>
            </div>
          )}

          {session?.status === "waiting_ask" && (
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 space-y-3">
              <h4 className="font-semibold text-amber-300">Confirmation Required</h4>
              <p className="text-ink font-medium text-sm">{session.ask_prompt}</p>
              <div className="flex items-center justify-end gap-2 pt-1">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => handleRespond("no")}
                  className="rounded-md border border-line px-3 py-1.5 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                >
                  No (Abort)
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => handleRespond("skip")}
                  className="rounded-md border border-line px-3 py-1.5 text-amber-400 hover:bg-amber-500/10 hover:text-amber-300"
                >
                  Skip
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => handleRespond("yes")}
                  className="rounded-md bg-indigo-600 px-4 py-1.5 font-medium text-white hover:bg-indigo-500"
                >
                  Yes (Execute)
                </button>
              </div>
            </div>
          )}

          {/* Completed / Aborted Final Banner */}
          {session?.status === "completed" && (
            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-emerald-300 flex items-center justify-between">
              <span>{session.final_message || "Workflow completed successfully."}</span>
              <button
                type="button"
                onClick={onClose}
                className="rounded-md bg-emerald-600 px-3 py-1 text-white hover:bg-emerald-500"
              >
                Done
              </button>
            </div>
          )}

          {session?.status === "aborted" && (
            <div className="rounded-lg border border-line bg-surface-strong p-3 text-ink-muted flex items-center justify-between">
              <span>{session.final_message || "Workflow aborted by user."}</span>
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-line px-3 py-1 hover:bg-elevated text-ink"
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
