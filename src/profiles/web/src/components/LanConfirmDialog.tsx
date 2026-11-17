import { setLanEnabled, waitForLanState, fetchSystemInfo } from "../api/client";
import type { SystemInfo } from "../api/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { CopyableUrl } from "./CopyableUrl";

export interface LanConfirmDialogProps {
  /** Tri-state: null = closed, true = enabling LAN access, false = restricting. */
  pending: boolean | null;
  systemInfo: SystemInfo | null;
  showToast: (msg: string, kind?: "info" | "error") => void;
  /** Called with the observed SystemInfo on both success and refetch paths. */
  onConfirmed: (sys: SystemInfo) => void;
  onCancel: () => void;
}

/**
 * LAN-toggle confirmation dialog — owns the observe-and-verify flow moved
 * verbatim from App.tsx: `setLanEnabled` → transitional toast →
 * `waitForLanState` (the rebind runs after the response, so the *observed*
 * state decides the outcome branch) → success/failure toast, or a rejected
 * bind → error toast + refetch. The api client is imported directly
 * (ConfigEditorModal precedent); toasts flow through the injected
 * `showToast` and observed state is reported via `onConfirmed(sys)`.
 *
 * The dialog-closes-first quirk is preserved: the confirm flow calls
 * `onCancel()` at its start — the same close action App already performs
 * (`setLanPending(null)`) — so the dialog disappears before the async work
 * and the flow still completes behind it.
 */
export function LanConfirmDialog({
  pending,
  systemInfo,
  showToast,
  onConfirmed,
  onCancel,
}: LanConfirmDialogProps) {
  return (
    <ConfirmDialog
      isOpen={pending !== null}
      title={pending ? "Enable LAN access?" : "Restrict to this machine?"}
      message={
        pending ? (
          <span className="block">
            ProFiles will be reachable by anyone on this network:
            <CopyableUrl
              url={`http://${systemInfo?.hostname}:${window.location.port}`}
              label="Copy hostname URL"
              className="mt-1.5"
              onCopied={() => showToast("URL copied to clipboard.")}
              onCopyError={() => showToast("Failed to copy URL.", "error")}
            />
            <CopyableUrl
              url={`http://${systemInfo?.ip}:${window.location.port}`}
              label="Copy IP URL"
              className="mt-1.5"
              onCopied={() => showToast("URL copied to clipboard.")}
              onCopyError={() => showToast("Failed to copy URL.", "error")}
            />
          </span>
        ) : (
          "ProFiles will be reachable only on this machine."
        )
      }
      confirmLabel={pending ? "Enable LAN" : "Restrict"}
      onConfirm={async () => {
        const next = pending!;
        // Dialog-closes-first: close through onCancel before the flow runs.
        onCancel();
        try {
          await setLanEnabled(next);
          showToast(
            next
              ? "Updating LAN binding…"
              : "Restricting ProFiles to this machine…",
            "info"
          );
          // The rebind runs after the response; observe the real outcome.
          const sys = await waitForLanState(next);
          if (sys) onConfirmed(sys);
          if (sys?.lan_enabled === next) {
            showToast(
              next
                ? "ProFiles is now reachable on the local network."
                : "ProFiles is restricted to this machine.",
              "info"
            );
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
      }}
      onCancel={onCancel}
    />
  );
}
