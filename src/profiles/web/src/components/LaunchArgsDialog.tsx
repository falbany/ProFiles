import { useEffect, useRef, useState } from "react";

interface LaunchArgsDialogProps {
  open: boolean;
  /** Name shown above the field: the file the arguments will launch. */
  filename: string;
  /** Called with the typed arguments on submit. The owner closes the dialog. */
  onSubmit: (args: string) => void;
  onClose: () => void;
}

/**
 * Ask for command-line arguments before a launch.
 *
 * A native `<dialog>`: `showModal()` gives the focus trap, top-layer
 * stacking, backdrop-click target and Escape/cancel handling that a raw
 * rendered-but-not-shown dialog lacked (issue #62). The arguments persist
 * across openings for as long as the app runs, as they did when this dialog
 * lived inside the context menu.
 */
export function LaunchArgsDialog({ open, filename, onSubmit, onClose }: LaunchArgsDialogProps) {
  const [argsValue, setArgsValue] = useState("");
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (open) {
      dialogRef.current?.showModal();
    }
  }, [open]);

  if (!open) return null;

  const handleSubmit = () => onSubmit(argsValue);

  return (
    <dialog
      ref={dialogRef}
      className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-center justify-center bg-black/60 p-4 rounded-xl"
      aria-labelledby="args-modal-title"
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose();
      }}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
    >
      <div className="animate-modal-in w-96 rounded-xl border border-frame-line glass-panel p-4">
        <h3 id="args-modal-title" className="mb-2 text-sm font-semibold text-ink">Launch with Arguments</h3>
        <p className="mb-3 text-xs text-ink-muted truncate">{filename}</p>
        <input
          type="text"
          autoFocus
          placeholder="Arguments (e.g. --verbose --port 80)"
          value={argsValue}
          onChange={(e) => setArgsValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit();
            if (e.key === "Escape") onClose();
          }}
          className="mb-4 w-full rounded-md border border-line bg-elevated px-3 py-2 text-xs text-ink outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500"
          aria-label="Command line arguments"
        />
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded-md px-3 py-1.5 text-xs text-ink-muted hover:bg-elevated hover:text-ink focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Cancel launch"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            className="btn btn-primary px-3 py-1.5"
            aria-label={`Launch ${filename} with arguments`}
          >
            Launch
          </button>
        </div>
      </div>
    </dialog>
  );
}
