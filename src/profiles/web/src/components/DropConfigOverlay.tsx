import { FileCog } from "lucide-react";
import { useRef } from "react";

interface DropConfigOverlayProps {
  visible: boolean;
  onFileSelected: (file: File) => void;
}

/** Full-window overlay shown while a config file is dragged over the app.

Clicking the overlay opens a file picker as an accessibility fallback.
Dismissal is owned by the parent (drag state lives at window level).
 */
export function DropConfigOverlay({ visible, onFileSelected }: DropConfigOverlayProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/65 backdrop-blur-sm"
      onClick={() => inputRef.current?.click()}
      data-testid="drop-config-overlay"
    >
      <input
        ref={inputRef}
        type="file"
        accept=".profiles,.profiles.yaml,.profiles.yml,.yaml,.yml"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFileSelected(file);
          e.target.value = "";
        }}
      />
      <div className="rounded-xl border-2 border-dashed border-chip-indigo-border bg-surface px-8 py-6 text-center shadow-2xl">
        <span className="mx-auto mb-3 grid h-9 w-9 place-items-center rounded-lg bg-chip-indigo-bg">
          <FileCog className="h-5 w-5 text-chip-indigo-text" />
        </span>
        <p className="text-sm font-semibold text-ink">Drop configuration file</p>
        <p className="mt-1 text-xs text-ink-muted">
          .profiles, .profiles.yaml, .yml, .yaml — session-only preview
        </p>
      </div>
    </div>
  );
}
