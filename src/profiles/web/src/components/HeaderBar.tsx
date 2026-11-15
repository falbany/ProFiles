import { useState } from "react";
import { ArrowRight, ChevronRight, Folder, FolderOpen, Home, Terminal } from "lucide-react";
import { EditableCombobox } from "./EditableCombobox";
import Tooltip from "./Tooltip";
import { shortVersion } from "../utils/version";

interface HeaderBarProps {
  title: string;
  release: string;
  directories: string[];
  activeDirectory: string;
  onDirectoryChange: (dir: string) => void;
  onBrowseDirectory?: () => void;
  onGoToParentDirectory?: () => void;
  onGoToHomeDirectory?: () => void;
  onOpenActiveDirectory?: () => void;
  onOpenTerminal?: (directory: string) => void;
}

export function HeaderBar({
  title,
  release,
  directories,
  activeDirectory,
  onDirectoryChange,
  onBrowseDirectory,
  onGoToParentDirectory,
  onGoToHomeDirectory,
  onOpenActiveDirectory,
  onOpenTerminal,
}: HeaderBarProps) {
  // Unfolded directory list — the tooltip yields to it (issue #53).
  const [dirListOpen, setDirListOpen] = useState(false);
  // Full version from hatch-vcs (issue #175) — only the short form is displayed.
  const fullVersion = release || __APP_VERSION__;
  return (
    <header className="relative z-30 flex flex-wrap items-center gap-3 border-b border-line bg-app/90 px-5 py-2 text-xs backdrop-blur-xl shadow-xs transition-all duration-200">
      <div className="flex shrink-0 items-center gap-3">
        <div className="flex items-center gap-3.5">
          {/* App logo from img/ (issue #173) — keep the status dot overlay. */}
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl border border-chip-indigo-border shadow-xs">
            <img src="/profiles-128.png" alt="ProFiles logo" className="h-9 w-9 rounded-xl object-cover" />
            <span className="absolute -bottom-0.5 -right-0.5 flex h-2.5 w-2.5 items-center justify-center rounded-full bg-emerald-500 ring-2 ring-app" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold tracking-tight text-ink font-heading">
                ProFiles
              </h1>
              {title && (
                <>
                  <span className="text-ink-faint">/</span>
                  <span className="text-xs font-medium text-chip-indigo-text bg-chip-indigo-bg px-2 py-0.5 rounded-md border border-chip-indigo-border/50">
                    {title}
                  </span>
                </>
              )}
            </div>
            <p className="text-[11px] font-medium text-ink-muted tracking-wide mt-0.5">
              Crafted by <span className="text-ink font-semibold">Florent ALBANY</span> •{" "}
              {/* hatch-vcs dev builds carry a long local version (issue #175):
                  show only the release part, the full string lives in the tooltip. */}
              <Tooltip text={`v${fullVersion}`} placement="bottom">
                <span className="font-mono text-chip-indigo-text">v{shortVersion(fullVersion)}</span>
              </Tooltip>
            </p>
          </div>
        </div>
      </div>

      {/* Directory selection — inline after the brand, fills the remaining space.
          The systemInfo pill moved to the StatusBar to free this room. */}
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <label className="flex shrink-0 items-center gap-1.5 font-medium text-ink-secondary text-xs">
          <Folder className="h-3.5 w-3.5 text-chip-indigo-text" />
          <span>Directory:</span>
        </label>
        <Tooltip text="Select or type a directory path to scan files from." suppress={dirListOpen}>
          <EditableCombobox
            id="directory-combobox"
            ariaLabel="Directory"
            value={activeDirectory}
            options={directories}
            onChange={onDirectoryChange}
            // Typing a path must not fire a server round-trip per keystroke
            // (issue #121): commit on Enter / blur / option pick instead.
            commitOn="deferred"
            onOpenChange={setDirListOpen}
            placeholder="/path/to/directory"
            className="w-full"
            inputClassName="font-mono"
          />
        </Tooltip>

        {/* Open active directory in OS file manager (left of Browse) */}
        {onOpenActiveDirectory && (
          <Tooltip text="Open the active directory in the OS file manager" block={false}>
            <button
              type="button"
              onClick={onOpenActiveDirectory}
              aria-label="Open active directory"
              className="btn btn-secondary shrink-0 p-1.5"
            >
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </Tooltip>
        )}

        {/* Go to parent directory (left of Browse) */}
        {onGoToParentDirectory && (
          <Tooltip text="Go to parent directory" block={false}>
            <button
              type="button"
              onClick={onGoToParentDirectory}
              aria-label="Go to parent directory"
              className="btn btn-secondary shrink-0 p-1.5"
            >
              <ChevronRight className="h-3.5 w-3.5 rotate-180" />
            </button>
          </Tooltip>
        )}

        {/* Browse for folder */}
        {onBrowseDirectory && (
          <Tooltip text="Browse for a folder on this system" block={false}>
            <button
              type="button"
              onClick={onBrowseDirectory}
              aria-label="Browse directory"
              className="btn btn-secondary shrink-0 p-1.5"
            >
              <FolderOpen className="h-3.5 w-3.5" />
            </button>
          </Tooltip>
        )}

        {/* Open active directory in terminal (right of Browse) */}
        {onOpenTerminal && (
          <Tooltip text="Open the active directory in a terminal" block={false}>
            <button
              type="button"
              onClick={() => onOpenTerminal(activeDirectory)}
              aria-label="Open directory in terminal"
              className="btn btn-secondary shrink-0 p-1.5"
            >
              <Terminal className="h-3.5 w-3.5" />
            </button>
          </Tooltip>
        )}

        {/* Go to user home directory (right of Terminal) */}
        {onGoToHomeDirectory && (
          <Tooltip text="Set directory to your home folder" block={false}>
            <button
              type="button"
              onClick={onGoToHomeDirectory}
              aria-label="Go to home directory"
              className="btn btn-secondary shrink-0 p-1.5"
            >
              <Home className="h-3.5 w-3.5" />
            </button>
          </Tooltip>
        )}
      </div>
    </header>
  );
}
