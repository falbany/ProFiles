import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, ExternalLink, Wifi, X } from "lucide-react";

import {
  fetchSystemInfo,
  generateBarcode,
  setLanEnabled,
  waitForLanState,
} from "../api/client";
import type { SystemInfo } from "../api/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { CopyableUrl } from "./CopyableUrl";
import { useModalA11y } from "../hooks/useModalA11y";

export interface LanConfirmDialogProps {
  /** Tri-state: null = closed, true = enabling LAN access, false = restricting. */
  pending: boolean | null;
  systemInfo: SystemInfo | null;
  showToast: (msg: string, kind?: "info" | "error") => void;
  /** Called with the observed SystemInfo on both success and refetch paths. */
  onConfirmed: (sys: SystemInfo) => void;
  onCancel: () => void;
}

/** Phases of the enable flow (issue #197): confirm → panel states. */
type EnablePhase = "confirm" | "enabling" | "enabled" | "failed";

/**
 * LAN-toggle dialog (issues #197/#198/#199). The two directions diverge:
 *
 * - **Restrict** keeps the old confirm-and-vanish dialog — the confirm flow
 *   calls `onCancel()` at its start, the dialog disappears before the async
 *   work, and the flow completes behind it with toast-only feedback.
 * - **Enable** keeps the modal open: confirming moves to a status panel
 *   (Enabling… → Enabled / Failed) that reports the rebind outcome inline.
 *   The copyable hostname/IP URLs survive the toggle, a clickable loopback
 *   link is offered in both phases, and the enabled panel shows a QR of the
 *   IP URL (`generateBarcode`, the files' "Generate QR Code" endpoint — no
 *   client-side dependency). Closing the panel mid-flow falls back to the
 *   toast channel: the async flow keeps running and reports through
 *   `onConfirmed(sys)` + toasts, exactly like the restrict path.
 *
 * The api client is imported directly (ConfigEditorModal precedent); toasts
 * flow through the injected `showToast` and observed state is reported via
 * `onConfirmed(sys)`. App's contract is unchanged — `onCancel()` still only
 * closes, it is simply no longer called by the enable flow itself.
 */
export function LanConfirmDialog({
  pending,
  systemInfo,
  showToast,
  onConfirmed,
  onCancel,
}: LanConfirmDialogProps) {
  const [phase, setPhase] = useState<EnablePhase>("confirm");
  const [failureMessage, setFailureMessage] = useState<string | null>(null);
  const [qrImage, setQrImage] = useState<string | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  /** Monotonic tag per confirm click — a slow stale flow must never paint
   *  over a reopened dialog (BarcodeModal's issue-#140 pattern). */
  const flowSeqRef = useRef(0);
  /** Mirror of "status panel visible", read by async completions to pick
   *  between inline state (open) and toasts (closed mid-flow). */
  const panelOpenRef = useRef(false);

  useEffect(() => {
    panelOpenRef.current = pending !== null && phase !== "confirm";
  }, [pending, phase]);

  // A reopened dialog always starts from the confirmation view and
  // invalidates any flow still in flight from a previous open.
  useEffect(() => {
    if (pending !== null) {
      flowSeqRef.current += 1;
      setPhase("confirm");
      setFailureMessage(null);
    }
  }, [pending]);

  const port = window.location.port;
  const hostnameUrl = systemInfo ? `http://${systemInfo.hostname}:${port}` : null;
  const ipUrl = systemInfo ? `http://${systemInfo.ip}:${port}` : null;
  const loopbackUrl = `http://127.0.0.1:${port}`;

  // QR for the IP URL (issue #198): generated once on entering the enabled
  // state — before the rebind the URL would scan into a dead address.
  useEffect(() => {
    if (phase !== "enabled" || !ipUrl) return;
    let cancelled = false;
    setQrImage(null);
    setQrError(null);
    generateBarcode({ content: ipUrl })
      .then((res) => {
        if (!cancelled) setQrImage(res.image);
      })
      .catch((err) => {
        if (!cancelled)
          setQrError(
            err instanceof Error ? err.message : "Failed to generate the QR code"
          );
      });
    return () => {
      cancelled = true;
    };
  }, [phase, ipUrl]);

  const panelIsOpen = pending !== null && phase !== "confirm";
  const handlePanelKeyDown = useModalA11y({
    isOpen: panelIsOpen,
    onClose: onCancel,
    dialogRef: panelRef,
    initialFocusRef: closeRef,
  });

  if (pending === null) return null;

  /** Restrict keeps the historical dialog-closes-first flow (toast-only). */
  const runRestrictFlow = async () => {
    // Dialog-closes-first: close through onCancel before the flow runs.
    onCancel();
    try {
      await setLanEnabled(false);
      showToast("Restricting ProFiles to this machine…", "info");
      // The rebind runs after the response; observe the real outcome.
      const sys = await waitForLanState(false);
      if (sys) onConfirmed(sys);
      if (sys?.lan_enabled === false) {
        showToast("ProFiles is restricted to this machine.", "info");
      } else {
        showToast(
          "Failed to update LAN binding — the previous address is still active.",
          "error"
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update LAN binding";
      showToast(`Failed to update LAN binding: ${msg}`, "error");
      // Refetch to restore the actual state
      const sys = await fetchSystemInfo();
      onConfirmed(sys);
    }
  };

  /** Enable keeps the modal open and reports inline (issue #197). */
  const runEnableFlow = async () => {
    const seq = ++flowSeqRef.current;
    setFailureMessage(null);
    setPhase("enabling");
    try {
      await setLanEnabled(true);
      // The rebind runs after the response; observe the real outcome.
      const sys = await waitForLanState(true);
      if (sys) onConfirmed(sys);
      if (seq !== flowSeqRef.current) return; // dialog was reopened meanwhile
      if (sys?.lan_enabled === true) {
        setPhase("enabled");
        if (!panelOpenRef.current) {
          showToast("ProFiles is now reachable on the local network.", "info");
        }
      } else {
        setPhase("failed");
        setFailureMessage(
          "Failed to update LAN binding — the previous address is still active."
        );
        if (!panelOpenRef.current) {
          showToast(
            "Failed to update LAN binding — the previous address is still active.",
            "error"
          );
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update LAN binding";
      if (seq !== flowSeqRef.current) return;
      setPhase("failed");
      setFailureMessage(`Failed to update LAN binding: ${msg}`);
      // Refetch to restore the actual state
      const sys = await fetchSystemInfo();
      onConfirmed(sys);
      if (!panelOpenRef.current) {
        showToast(`Failed to update LAN binding: ${msg}`, "error");
      }
    }
  };

  if (pending === false) {
    return (
      <ConfirmDialog
        isOpen
        title="Restrict to this machine?"
        message="ProFiles will be reachable only on this machine."
        confirmLabel="Restrict"
        onConfirm={() => void runRestrictFlow()}
        onCancel={onCancel}
      />
    );
  }

  if (phase === "confirm") {
    return (
      <ConfirmDialog
        isOpen
        title="Enable LAN access?"
        message={
          <span className="block">
            ProFiles will be reachable by anyone on this network:
            {hostnameUrl && (
              <CopyableUrl
                url={hostnameUrl}
                label="Copy hostname URL"
                className="mt-1.5"
                onCopied={() => showToast("URL copied to clipboard.")}
                onCopyError={() => showToast("Failed to copy URL.", "error")}
              />
            )}
            {ipUrl && (
              <CopyableUrl
                url={ipUrl}
                label="Copy IP URL"
                className="mt-1.5"
                onCopied={() => showToast("URL copied to clipboard.")}
                onCopyError={() => showToast("Failed to copy URL.", "error")}
              />
            )}
            <span className="mt-1.5 flex items-center gap-1.5">
              <ExternalLink className="h-3.5 w-3.5 shrink-0 text-ink-faint" aria-hidden="true" />
              <a
                href={loopbackUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="break-all font-mono text-[11px] text-ink underline decoration-line underline-offset-2 hover:text-indigo-400"
              >
                {loopbackUrl}
              </a>
            </span>
          </span>
        }
        confirmLabel="Enable LAN"
        onConfirm={() => void runEnableFlow()}
        onCancel={onCancel}
      />
    );
  }

  // Status panel — Enabling… / Enabled / Failed (issue #197).
  return (
    <div
      className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onCancel}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="lan-panel-title"
        onKeyDown={handlePanelKeyDown}
        onClick={(e) => e.stopPropagation()}
        className="animate-modal-in w-[400px] max-w-full rounded-2xl border border-frame-line glass-panel p-5"
      >
        <div className="mb-4 flex items-center gap-2.5">
          <span
            className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${
              phase === "enabled"
                ? "bg-status-success-bg text-status-success-text"
                : phase === "failed"
                  ? "bg-status-danger-bg text-status-danger-text"
                  : "bg-chip-indigo-bg text-chip-indigo-text"
            }`}
          >
            {phase === "enabled" ? (
              <Check className="h-5 w-5" />
            ) : phase === "failed" ? (
              <AlertTriangle className="h-5 w-5" />
            ) : (
              <Wifi className="h-5 w-5" />
            )}
          </span>
          <h2 id="lan-panel-title" className="flex-1 text-sm font-semibold text-ink">
            {phase === "enabling"
              ? "Enabling LAN…"
              : phase === "enabled"
                ? "LAN access enabled"
                : "LAN update failed"}
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onCancel}
            aria-label="Close"
            title="Close"
            className="focus-ring rounded-md p-1 text-ink-muted hover:bg-elevated hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {phase === "enabling" && (
          <div className="flex items-center gap-3 py-2 text-xs text-ink-secondary">
            <span
              className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent"
              aria-hidden="true"
            />
            Updating the LAN binding — the panel reports the outcome.
          </div>
        )}

        {phase === "enabled" && (
          <div className="space-y-3 text-xs text-ink-secondary">
            <p className="flex items-center gap-1.5 text-ink">
              <Check className="h-3.5 w-3.5 text-status-success-text" aria-hidden="true" />
              ProFiles is reachable on this network.
            </p>
            <p>On another device on this network, open one of these addresses:</p>
            {hostnameUrl && (
              <CopyableUrl
                url={hostnameUrl}
                label="Copy hostname URL"
                onCopied={() => showToast("URL copied to clipboard.")}
                onCopyError={() => showToast("Failed to copy URL.", "error")}
              />
            )}
            {ipUrl && (
              <CopyableUrl
                url={ipUrl}
                label="Copy IP URL"
                onCopied={() => showToast("URL copied to clipboard.")}
                onCopyError={() => showToast("Failed to copy URL.", "error")}
              />
            )}
            <span className="flex items-center gap-1.5">
              <ExternalLink className="h-3.5 w-3.5 shrink-0 text-ink-faint" aria-hidden="true" />
              <a
                href={loopbackUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="break-all font-mono text-[11px] text-ink underline decoration-line underline-offset-2 hover:text-indigo-400"
              >
                {loopbackUrl}
              </a>
            </span>
            <div className="flex flex-col items-center gap-1.5 pt-1">
              <div className="h-40 w-40 overflow-hidden rounded-lg border border-line bg-white p-2">
                {qrImage ? (
                  <img
                    src={qrImage}
                    alt="QR code of the LAN address"
                    className="h-full w-full object-contain"
                  />
                ) : qrError ? (
                  <span
                    role="alert"
                    className="flex h-full items-center justify-center px-1 text-center text-[10px] text-status-danger-text"
                  >
                    {qrError}
                  </span>
                ) : (
                  <span
                    className="flex h-full items-center justify-center text-[10px] text-ink-faint"
                    aria-hidden="true"
                  >
                    …
                  </span>
                )}
              </div>
              <p className="text-[10px] text-ink-faint">Scan to connect from a phone.</p>
            </div>
          </div>
        )}

        {phase === "failed" && (
          <div
            role="alert"
            className="rounded-md border border-status-danger-border bg-status-danger-bg p-3 text-xs text-status-danger-text"
          >
            {failureMessage}
          </div>
        )}
      </div>
    </div>
  );
}
