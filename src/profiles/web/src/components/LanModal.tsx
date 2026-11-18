import { useEffect, useRef, useState } from "react";
import { ExternalLink, Wifi, WifiOff, X } from "lucide-react";

import {
  fetchSystemInfo,
  generateBarcode,
  setLanEnabled,
  waitForLanState,
} from "../api/client";
import type { SystemInfo } from "../api/types";
import { CopyableUrl } from "./CopyableUrl";
import { useModalA11y } from "../hooks/useModalA11y";

export interface LanModalProps {
  /** Whether the modal is shown; the flow keeps running after a close. */
  open: boolean;
  systemInfo: SystemInfo | null;
  showToast: (msg: string, kind?: "info" | "error") => void;
  /** Called with the observed SystemInfo on both success and refetch paths. */
  onConfirmed: (sys: SystemInfo) => void;
  onClose: () => void;
}

/** Direction of an in-flight bind change. */
type Busy = "enable" | "disable" | null;

/**
 * LAN access modal (issues #197/#198/#199) — ONE modal for both directions,
 * same UX for enabling and disabling (user decision on PR #200): it reflects
 * the live `systemInfo.lan_enabled` and offers the opposite action in the
 * footer ("Enable LAN" / "Disable LAN"), which runs in place — the modal
 * stays open through the rebind and reports the outcome inline (busy status
 * or failure box) instead of closing first. No direction is passed in: the
 * modal derives everything from the observed state.
 *
 * Layout: the QR of the IP URL sits on the LEFT and is always displayed,
 * even while LAN is disabled (user decision overriding #198's original
 * gating) — it reuses `generateBarcode` / `POST /api/actions/barcode` like
 * the files' "Generate QR Code", no client-side dependency. The header
 * carries the live status — icon chip (Wifi / WifiOff) plus "LAN Access —
 * Reachable on this network." / "LAN Access — Restricted to the host
 * machine." — so the body holds only the addresses: the copyable hostname
 * + IP URLs and the clickable loopback link (#199), spaced clear of the IP
 * row. ❌ (header) and Escape close at any time; footer buttons never
 * disappear — the action disables while a rebind is in flight.
 *
 * Closing mid-flow falls back to the toast channel: the async flow keeps
 * running and reports via `onConfirmed(sys)` + toasts, so App state stays in
 * sync. A stale flow can never paint over a reopened modal (BarcodeModal's
 * issue-#140 seq pattern). The api client is imported directly
 * (ConfigEditorModal precedent); toasts flow through the injected
 * `showToast` and observed state is reported via `onConfirmed(sys)`.
 */
export function LanModal({
  open,
  systemInfo,
  showToast,
  onConfirmed,
  onClose,
}: LanModalProps) {
  const [busy, setBusy] = useState<Busy>(null);
  const [failureMessage, setFailureMessage] = useState<string | null>(null);
  const [qrImage, setQrImage] = useState<string | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  /** Monotonic tag per action click — a slow stale flow must never paint
   *  over a reopened modal (BarcodeModal's issue-#140 pattern). */
  const seqRef = useRef(0);
  /** Mirror of `open`, read by async completions to pick between inline
   *  state (open) and toasts (closed mid-flow). */
  const openRef = useRef(false);

  useEffect(() => {
    openRef.current = open;
  }, [open]);

  // A reopened modal clears transient state and invalidates any flow still
  // in flight from a previous open.
  useEffect(() => {
    if (open) {
      seqRef.current += 1;
      setBusy(null);
      setFailureMessage(null);
    }
  }, [open]);

  const port = window.location.port;
  const hostnameUrl = systemInfo ? `http://${systemInfo.hostname}:${port}` : null;
  const ipUrl = systemInfo ? `http://${systemInfo.ip}:${port}` : null;
  const loopbackUrl = `http://127.0.0.1:${port}`;
  const liveEnabled = systemInfo?.lan_enabled === true;

  // QR of the IP URL (#198): always displayed, so generate while open and
  // the IP is known — the content does not depend on the bind state.
  useEffect(() => {
    if (!open || !ipUrl) return;
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
  }, [open, ipUrl]);

  const handleDialogKeyDown = useModalA11y({
    isOpen: open,
    onClose,
    dialogRef,
    initialFocusRef: cancelRef,
  });

  if (!open) return null;

  /** Toggle the bind in place — same UX for both directions. */
  const runToggleFlow = async (next: boolean) => {
    const seq = ++seqRef.current;
    setFailureMessage(null);
    setBusy(next ? "enable" : "disable");
    try {
      await setLanEnabled(next);
      // The rebind runs after the response; observe the real outcome.
      const sys = await waitForLanState(next);
      if (sys) onConfirmed(sys);
      if (seq !== seqRef.current) return; // modal was reopened meanwhile
      setBusy(null);
      if (sys?.lan_enabled === next) {
        if (!openRef.current) {
          showToast(
            next
              ? "ProFiles is now reachable on the local network."
              : "ProFiles is restricted to this machine.",
            "info"
          );
        }
      } else {
        setFailureMessage(
          "Failed to update LAN binding — the previous address is still active."
        );
        if (!openRef.current) {
          showToast(
            "Failed to update LAN binding — the previous address is still active.",
            "error"
          );
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to update LAN binding";
      if (seq !== seqRef.current) return;
      setBusy(null);
      setFailureMessage(`Failed to update LAN binding: ${msg}`);
      // Refetch to restore the actual state
      const sys = await fetchSystemInfo();
      onConfirmed(sys);
      if (!openRef.current) {
        showToast(`Failed to update LAN binding: ${msg}`, "error");
      }
    }
  };

  return (
    <div
      className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="lan-modal-title"
        onKeyDown={handleDialogKeyDown}
        onClick={(e) => e.stopPropagation()}
        className="animate-modal-in w-[480px] max-w-full rounded-2xl border border-frame-line glass-panel p-5"
      >
        <div className="mb-4 flex items-center gap-2.5">
          <span
            className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${
              liveEnabled
                ? "bg-status-success-bg text-status-success-text"
                : "bg-elevated text-ink-muted"
            }`}
          >
            {liveEnabled ? (
              <Wifi className="h-5 w-5" />
            ) : (
              <WifiOff className="h-5 w-5" />
            )}
          </span>
          <h2 id="lan-modal-title" className="flex-1 text-sm font-semibold text-ink">
            LAN Access —{" "}
            {liveEnabled
              ? "Reachable on this network."
              : "Restricted to the host machine."}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            title="Close"
            className="focus-ring rounded-md p-1 text-ink-muted hover:bg-elevated hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-start gap-4">
          {/* QR column — always displayed (user decision on PR #200). */}
          <div className="flex w-40 shrink-0 flex-col items-center gap-1.5">
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
            <p className="text-center text-[10px] text-ink-faint">
              Scan to connect from a phone.
            </p>
          </div>

          {/* Addresses column — status lives in the header now; explicit
              margins keep the loopback row clear of the IP row. */}
          <div className="min-w-0 flex-1 text-xs text-ink-secondary">
            {busy !== null && (
              <p className="flex items-center gap-2 text-ink">
                <span
                  className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent"
                  aria-hidden="true"
                />
                Updating the LAN binding…
              </p>
            )}
            {busy === null && failureMessage && (
              <div
                role="alert"
                className="rounded-md border border-status-danger-border bg-status-danger-bg p-2.5 text-status-danger-text"
              >
                {failureMessage}
              </div>
            )}
            {hostnameUrl && (
              <CopyableUrl
                url={hostnameUrl}
                label="Copy hostname URL"
                className="mt-3"
                onCopied={() => showToast("URL copied to clipboard.")}
                onCopyError={() => showToast("Failed to copy URL.", "error")}
              />
            )}
            {ipUrl && (
              <CopyableUrl
                url={ipUrl}
                label="Copy IP URL"
                className="mt-2"
                onCopied={() => showToast("URL copied to clipboard.")}
                onCopyError={() => showToast("Failed to copy URL.", "error")}
              />
            )}
            <span className="mt-4 flex items-center gap-1.5">
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
          </div>
        </div>

        {/* Footer buttons never disappear (#197 override): the action flips
            with the live state and disables while a rebind is in flight. */}
        <div className="mt-4 flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onClose}
            className="min-h-9 rounded-lg border border-line bg-elevated px-3.5 text-sm text-ink-secondary transition-colors hover:bg-surface-strong hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={busy !== null}
            onClick={() => void runToggleFlow(!liveEnabled)}
            className={`min-h-9 rounded-lg border px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 disabled:cursor-not-allowed disabled:opacity-50 ${
              liveEnabled
                ? "border-status-danger-border bg-status-danger-bg/30 text-status-danger-text hover:bg-status-danger-bg/60"
                : "btn-primary border-transparent bg-indigo-600 text-white hover:bg-indigo-500"
            }`}
          >
            {liveEnabled ? "Disable LAN" : "Enable LAN"}
          </button>
        </div>
      </div>
    </div>
  );
}
