import { ArrowRight, Folder, FolderOpen, Home, Terminal } from "lucide-react";
import { EditableCombobox } from "./EditableCombobox";
import Tooltip from "./Tooltip";

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
  return (
    <header className="relative z-30 flex flex-wrap items-center gap-3 border-b border-line bg-app/90 px-5 py-2 text-xs backdrop-blur-xl shadow-xs transition-all">
      <div className="flex shrink-0 items-center gap-3">
        <div className="flex items-center gap-3.5">
          <div className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 text-indigo-400 border border-indigo-500/30 shadow-xs">
            <Terminal className="h-4 w-4" />
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
                  <span className="text-xs font-medium text-indigo-400/90 bg-indigo-500/10 px-2 py-0.5 rounded-md border border-indigo-500/20">
                    {title}
                  </span>
                </>
              )}
            </div>
            <p className="text-[11px] font-medium text-ink-muted tracking-wide mt-0.5">
              Crafted by <span className="text-ink font-semibold">Florent ALBANY</span> • <span className="font-mono text-indigo-400">v{release || __APP_VERSION__}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Directory selection — inline after the brand, fills the remaining space.
          The systemInfo pill moved to the StatusBar to free this room. */}
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <label className="flex shrink-0 items-center gap-1.5 font-medium text-ink-secondary text-xs">
          <Folder className="h-3.5 w-3.5 text-indigo-400" />
          <span>Directory:</span>
        </label>
        <Tooltip text="Select or type a directory path to scan files from.">
          <EditableCombobox
            id="directory-combobox"
            ariaLabel="Directory"
            value={activeDirectory}
            options={directories}
            onChange={onDirectoryChange}
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
              className="flex shrink-0 items-center justify-center rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors"
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
              className="flex shrink-0 items-center justify-center rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors"
            >
              <span className="font-mono text-sm leading-none font-bold">&lt;</span>
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
              className="flex shrink-0 items-center justify-center rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors"
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
              className="flex shrink-0 items-center justify-center rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors"
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
              className="flex shrink-0 items-center justify-center rounded-md border border-line bg-elevated p-1.5 text-ink-secondary hover:border-indigo-500 hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 transition-colors"
            >
              <Home className="h-3.5 w-3.5" />
            </button>
          </Tooltip>
        )}
      </div>
    </header>
  );
}
