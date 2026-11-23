import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent } from "react";
import { FileCode, Search, X } from "lucide-react";

import type { ScannedFileItem } from "../api/types";
import { useModalA11y } from "../hooks/useModalA11y";
import {
  COMMAND_GROUP_LABELS,
  COMMAND_GROUP_ORDER,
  commandScore,
  fileScore,
  formatKeys,
  rankCommands,
  rankFiles,
} from "../utils/commands";
import type { Command } from "../utils/commands";
import { parentDirectory } from "../utils/fileProperties";

export interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  /** The command catalog (`useAppCommands`). */
  commands: Command[];
  /** Loaded rows searched by the quick-open list. */
  files: ScannedFileItem[];
  onOpenFile: (file: ScannedFileItem) => void;
  /** Ids of recently used commands, newest first. */
  recentIds: readonly string[];
  /** Called with a command's id each time it is run from the palette. */
  onCommandUsed: (id: string) => void;
}

/** Matching commands shown for a query. */
const COMMAND_RESULTS_LIMIT = 12;
/** Matching files shown for a query. */
const FILE_RESULTS_LIMIT = 8;

type PaletteRow =
  | { kind: "command"; key: string; command: Command }
  | { kind: "file"; key: string; file: ScannedFileItem };

interface PaletteSection {
  id: string;
  label: string;
  rows: PaletteRow[];
}

const commandRow = (command: Command): PaletteRow => ({
  kind: "command",
  key: `command:${command.id}`,
  command,
});

const fileRow = (file: ScannedFileItem): PaletteRow => ({
  kind: "file",
  key: `file:${file.path}`,
  file,
});

const isRunnable = (row: PaletteRow): boolean =>
  row.kind === "file" || row.command.enabled;

/**
 * The sections shown for a query. Without a query the palette is an
 * overview: recent commands first, then every palette command under its
 * group (files are only ever searched, never listed). With a query it is a
 * result list: matching commands, then matching files.
 */
function buildSections(
  commands: Command[],
  files: ScannedFileItem[],
  query: string,
  recentIds: readonly string[],
): PaletteSection[] {
  const paletteCommands = commands.filter((command) => command.palette !== false);

  if (!query.trim()) {
    const sections: PaletteSection[] = [];
    const recent = recentIds
      .map((id) => paletteCommands.find((command) => command.id === id))
      .filter((command): command is Command => command !== undefined);
    if (recent.length) {
      sections.push({ id: "recent", label: "Recent", rows: recent.map(commandRow) });
    }
    for (const group of COMMAND_GROUP_ORDER) {
      const rows = paletteCommands
        .filter((command) => command.group === group && !recent.includes(command))
        .map(commandRow);
      if (rows.length) {
        sections.push({ id: group, label: COMMAND_GROUP_LABELS[group], rows });
      }
    }
    return sections;
  }

  const sections: PaletteSection[] = [];
  const matchedCommands = rankCommands(commands, query, recentIds, COMMAND_RESULTS_LIMIT);
  const matchedFiles = rankFiles(files, query, FILE_RESULTS_LIMIT);
  if (!matchedCommands.length && !matchedFiles.length) return sections;

  // Both result lists are sorted best-first, so their first entry carries
  // the section's top score. The better match leads: a query that names a
  // file must not put a weak, incidental command match above it — Enter
  // would run that command instead of opening the file.
  const topScore = (score: number | null): number => (score === null ? -Infinity : score);
  const filesLead =
    matchedFiles.length > 0 &&
    topScore(fileScore(matchedFiles[0], query)) > topScore(
      matchedCommands.length ? commandScore(matchedCommands[0], query) : null,
    );

  const commandSection = (): PaletteSection | null =>
    matchedCommands.length
      ? { id: "commands", label: "Commands", rows: matchedCommands.map(commandRow) }
      : null;
  const fileSection = (): PaletteSection | null =>
    matchedFiles.length ? { id: "files", label: "Files", rows: matchedFiles.map(fileRow) } : null;

  const ordered = filesLead ? [fileSection(), commandSection()] : [commandSection(), fileSection()];
  for (const section of ordered) {
    if (section) sections.push(section);
  }
  return sections;
}

const clamp = (value: number, min: number, max: number): number =>
  Math.min(Math.max(value, min), max);

/**
 * Command palette (issue #224): one surface to find and run any command, and
 * to jump to a loaded file by name.
 *
 * Layout is fixed — search field on top, a constant-height result area, a
 * key-hint footer — so nothing moves between queries. Commands that cannot
 * run right now stay listed, dimmed with the reason, and are skipped by the
 * arrow keys; they are never hidden (a control that disappears between
 * states reads as a bug).
 *
 * Running happens in a fixed order: close, then run. Closing restores focus
 * to whatever was focused before the palette opened, and that restore would
 * undo a command that moves focus or opens a dialog if it ran first.
 */
export function CommandPalette({
  isOpen,
  onClose,
  commands,
  files,
  onOpenFile,
  recentIds,
  onCommandUsed,
}: CommandPaletteProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const handleDialogKeyDown = useModalA11y({
    isOpen,
    onClose,
    dialogRef,
    initialFocusRef: inputRef,
  });

  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  // A fresh start on every open: the previous query must not greet the user
  // again. (React's "adjust state during render when a prop changes" idiom.)
  const [wasOpen, setWasOpen] = useState(false);
  if (isOpen !== wasOpen) {
    setWasOpen(isOpen);
    if (isOpen) {
      setQuery("");
      setActiveIndex(0);
    }
  }

  const sections = useMemo(
    () => buildSections(commands, files, query, recentIds),
    [commands, files, query, recentIds],
  );
  const rows = useMemo(() => sections.flatMap((section) => section.rows), [sections]);
  const runnable = useMemo(() => rows.filter(isRunnable), [rows]);
  const activeRow: PaletteRow | undefined =
    runnable.length > 0 ? runnable[clamp(activeIndex, 0, runnable.length - 1)] : undefined;

  // Keep the active row in view when it is moved with the keyboard.
  useEffect(() => {
    if (!activeRow) return;
    const element = listRef.current?.querySelector<HTMLElement>('[data-active="true"]');
    // jsdom has no scrollIntoView; the guard keeps the component testable.
    element?.scrollIntoView?.({ block: "nearest" });
  }, [activeRow]);

  const activate = (row: PaletteRow): void => {
    if (!isRunnable(row)) return;
    onClose();
    window.setTimeout(() => {
      if (row.kind === "command") {
        onCommandUsed(row.command.id);
        row.command.run();
      } else {
        onOpenFile(row.file);
      }
    }, 0);
  };

  const handleInputKeyDown = (event: ReactKeyboardEvent<HTMLInputElement>): void => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const delta = event.key === "ArrowDown" ? 1 : -1;
      setActiveIndex((previous) => clamp(previous + delta, 0, Math.max(runnable.length - 1, 0)));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (activeRow) activate(activeRow);
    }
  };

  const paletteCount = useMemo(
    () => commands.filter((command) => command.palette !== false).length,
    [commands],
  );

  if (!isOpen) return null;

  const rowId = (index: number): string => `command-palette-option-${index}`;
  const activeKey = activeRow?.key;
  const indexOfActive = rows.findIndex((row) => row.key === activeKey);

  return (
    <div
      className="animate-overlay-in fixed inset-0 z-[var(--z-modal)] flex items-start justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        onKeyDown={handleDialogKeyDown}
        onClick={(event) => event.stopPropagation()}
        className="animate-modal-in mt-[8vh] flex w-[620px] max-w-full flex-col overflow-hidden rounded-2xl border border-frame-line glass-panel"
      >
        {/* Search row */}
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Search className="h-4 w-4 shrink-0 text-ink-faint" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            role="combobox"
            aria-label="Search commands and files"
            aria-expanded="true"
            aria-controls="command-palette-results"
            aria-autocomplete="list"
            aria-activedescendant={activeRow && indexOfActive >= 0 ? rowId(indexOfActive) : undefined}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
              setActiveIndex(0);
            }}
            onKeyDown={handleInputKeyDown}
            placeholder="Type a command or a file name…"
            spellCheck={false}
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent py-3 text-sm text-ink placeholder:text-ink-faint focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close the command palette"
            className="focus-ring shrink-0 rounded-lg p-1 text-ink-muted hover:bg-elevated hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Results — fixed height so the footer never moves */}
        <div
          id="command-palette-results"
          ref={listRef}
          role="listbox"
          aria-label="Results"
          className="h-[min(46vh,400px)] overflow-y-auto py-1 text-xs"
        >
          {rows.length === 0 ? (
            <p className="flex h-full items-center justify-center px-6 text-center text-ink-faint">
              No command or file matches “{query.trim()}”.
            </p>
          ) : (
            sections.map((section) => (
              <div key={section.id} role="group" aria-label={section.label}>
                <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
                  {section.label}
                </div>
                {section.rows.map((row) => {
                  const index = rows.indexOf(row);
                  const active = row.key === activeKey;
                  const runnableRow = isRunnable(row);
                  return (
                    <div
                      key={row.key}
                      id={rowId(index)}
                      role="option"
                      aria-selected={active}
                      aria-disabled={!runnableRow}
                      data-active={active || undefined}
                      onMouseMove={() => {
                        const runnableIndex = runnable.indexOf(row);
                        if (runnableIndex >= 0) setActiveIndex(runnableIndex);
                      }}
                      // Keep the caret in the search field: focus is the
                      // palette's, the pointer only picks a row.
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => activate(row)}
                      className={`flex items-center gap-2 px-3 py-1.5 ${
                        active ? "bg-chip-indigo-bg text-ink" : "text-ink-secondary"
                      } ${runnableRow ? "cursor-pointer" : "cursor-not-allowed opacity-50"}`}
                    >
                      {row.kind === "file" ? (
                        <FileCode className="h-3.5 w-3.5 shrink-0 text-chip-indigo-text" aria-hidden="true" />
                      ) : (
                        <span className="w-3.5 shrink-0" aria-hidden="true" />
                      )}
                      <span className="min-w-0 flex-1 truncate">
                        {row.kind === "file" ? row.file.filename : row.command.title}
                      </span>
                      {row.kind === "file" ? (
                        <span className="min-w-0 max-w-[45%] truncate text-[11px] text-ink-faint">
                          {parentDirectory(row.file.rel_path) || "."}
                        </span>
                      ) : row.command.enabled ? (
                        row.command.keys?.length ? (
                          <kbd className="shrink-0 rounded border border-line bg-app px-2 py-0.5 font-mono text-[11px] font-semibold text-chip-indigo-text">
                            {formatKeys(row.command.keys)}
                          </kbd>
                        ) : null
                      ) : (
                        <span className="shrink-0 text-[11px] text-ink-faint">
                          {row.command.disabledReason}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer — one place for the key hints */}
        <div className="flex items-center justify-between border-t border-line px-3 py-2 text-[10px] text-ink-faint">
          <span className="flex items-center gap-1.5">
            <kbd className="rounded border border-line bg-app px-1 font-mono text-ink-muted">↑</kbd>
            <kbd className="rounded border border-line bg-app px-1 font-mono text-ink-muted">↓</kbd>
            <span className="mr-2">Move</span>
            <kbd className="rounded border border-line bg-app px-1 font-mono text-ink-muted">Enter</kbd>
            <span className="mr-2">Run</span>
            <kbd className="rounded border border-line bg-app px-1 font-mono text-ink-muted">Esc</kbd>
            <span>Close</span>
          </span>
          <span>
            {paletteCount} command{paletteCount === 1 ? "" : "s"}
          </span>
        </div>
      </div>
    </div>
  );
}
