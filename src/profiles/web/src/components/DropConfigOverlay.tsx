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
      className="fixed inset-0 z-40 flex cursor-copy items-center justify-center bg-black/70 backdrop-blur-sm"
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
      <div className="rounded-lg border-2 border-dashed border-indigo-400 bg-slate-900/90 px-8 py-6 text-center">
        <p className="text-sm font-semibold text-ink">Drop configuration file</p>
        <p className="mt-1 text-xs text-muted">
          .profiles, .profiles.yaml, .yml, .yaml — session-only preview
        </p>
      </div>
    </div>
  );
}
