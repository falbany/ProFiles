import { useRef } from "react";
import { Keyboard, X } from "lucide-react";

import { useModalA11y } from "../hooks/useModalA11y";
import { COMMAND_GROUP_LABELS, COMMAND_GROUP_ORDER, formatKeys } from "../utils/commands";
import type { Command } from "../utils/commands";

interface ShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** The command catalog (`useAppCommands`) — every keyed command is listed. */
  commands: Command[];
}

/**
 * Keys that belong to a dialog rather than to a command: the workflow
 * runner answers its own guard, and Escape closes whatever is open.
 */
const DIALOG_KEYS: { key: string; desc: string }[] = [
  { key: "Y / S / N", desc: "Answer workflow guard: Yes / Skip / No (prompt open)" },
  { key: "Enter", desc: "Confirm active workflow prompt (prompt open)" },
  { key: "Escape", desc: "Close dialogs / context menu" },
];

function ShortcutRow({ desc, shortcut }: { desc: string; shortcut: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-elevated/50 px-3 py-2">
      <span className="text-ink-secondary">{desc}</span>
      <kbd className="rounded bg-app px-2 py-0.5 font-mono text-[11px] font-semibold text-chip-indigo-text border border-line">
        {shortcut}
      </kbd>
    </div>
  );
}

/**
 * Keyboard shortcuts reference (issue #62 modal, fed from the command
 * registry since issue #224). The table IS the registry: a command with a
 * key binding is listed here by construction, so a shortcut can no longer be
 * advertised without being bound (the #56 drift) or bound without being
 * listed. Commands without keys — and their enabled state — do not belong
 * on a shortcut sheet and are left out.
 */
export function ShortcutsModal({ isOpen, onClose, commands }: ShortcutsModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const handleDialogKeyDown = useModalA11y({ isOpen, onClose, dialogRef });

  if (!isOpen) return null;

  const sections = COMMAND_GROUP_ORDER.map((group) => ({
    group,
    rows: commands.filter((command) => command.group === group && command.keys?.length),
  })).filter((section) => section.rows.length > 0);

  return (
    <div className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Keyboard Shortcuts"
        onKeyDown={handleDialogKeyDown}
        className="animate-modal-in w-[450px] max-w-full rounded-2xl border border-frame-line glass-panel p-5"
      >
        <div className="mb-4 flex items-center justify-between border-b border-line pb-3">
          <div className="flex items-center gap-2 font-semibold text-ink">
            <Keyboard className="h-5 w-5 text-chip-indigo-text" />
            <span>Keyboard Shortcuts</span>
          </div>
          <button
            onClick={onClose}
            className="focus-ring rounded-lg p-1 text-ink-muted hover:bg-elevated hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-[60vh] space-y-3 overflow-y-auto pr-1 text-xs">
          {sections.map(({ group, rows }) => (
            <section key={group} aria-label={COMMAND_GROUP_LABELS[group]}>
              <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
                {COMMAND_GROUP_LABELS[group]}
              </div>
              <div className="space-y-2">
                {rows.map((command) => (
                  <ShortcutRow
                    key={command.id}
                    desc={command.title}
                    shortcut={formatKeys(command.keys)}
                  />
                ))}
              </div>
            </section>
          ))}

          <section aria-label="In dialogs">
            <div className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
              In dialogs
            </div>
            <div className="space-y-2">
              {DIALOG_KEYS.map(({ key, desc }) => (
                <ShortcutRow key={key} desc={desc} shortcut={key} />
              ))}
            </div>
          </section>
        </div>

        <div className="mt-5 flex justify-end">
          <button
            onClick={onClose}
            className="btn btn-primary rounded-lg px-4 py-2 font-semibold"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
