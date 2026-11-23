/**
 * Command registry primitives (issue #224) — the single source of truth
 * shared by the global key handler (`useGlobalShortcuts`), the keyboard
 * shortcuts modal and the command palette.
 *
 * A `Command` couples what an action IS (id, title, group, key bindings)
 * with how it RUNS right now (`enabled`, `run`). Because the palette, the
 * shortcuts table and the key handler all read the same objects, a shortcut
 * can no longer be advertised without being bound (the #56 drift) or bound
 * without being discoverable.
 *
 * This module is stateless: pure helpers over command lists.
 */

import type { ScannedFileItem } from "../api/types";

/**
 * One key binding. Modifier flags are tri-state on purpose:
 * `true` requires the modifier, `false` requires its absence, `undefined`
 * does not look at it. The original keydown handler checked Shift for some
 * bindings (L, K, T, B) and ignored it for others (R, D, E, F, H, comma) —
 * `undefined` is what keeps that behaviour bit-exact instead of silently
 * redefining which combinations fire.
 */
export interface ShortcutSpec {
  /** `KeyboardEvent.key`, compared case-insensitively. */
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
}

export type CommandGroup =
  | "file-list"
  | "selection"
  | "navigation"
  | "focus"
  | "view"
  | "configuration"
  | "tools";

/** Display names of the groups, in the order the palette shows them. */
export const COMMAND_GROUP_LABELS: Record<CommandGroup, string> = {
  "file-list": "File list",
  selection: "Selected file",
  navigation: "Directory",
  focus: "Focus",
  view: "View",
  configuration: "Configuration",
  tools: "Tools",
};

export const COMMAND_GROUP_ORDER: CommandGroup[] = [
  "file-list",
  "selection",
  "navigation",
  "view",
  "configuration",
  "tools",
  "focus",
];

export interface Command {
  /** Stable identifier — also the key the palette remembers recents by. */
  id: string;
  title: string;
  group: CommandGroup;
  /** Global key bindings. The first command in list order whose binding matches runs. */
  keys?: ShortcutSpec[];
  /** Extra terms the palette matches on (synonyms, legacy labels). */
  keywords?: string[];
  /** `false` hides the command from the palette (pure key bindings such as list navigation). */
  palette?: boolean;
  /** Runs before the target guards — i.e. also while focus sits in an input or on a control. */
  beforeTargetGuard?: boolean;
  /** Enter typed inside a text input or select also runs this command. */
  fromInputEnter?: boolean;
  /** False when the command cannot run right now: still listed, never fired. */
  enabled: boolean;
  /** Shown in place of the shortcut while the command is disabled. */
  disabledReason?: string;
  run: () => void;
}

/** The subset of a keyboard event the matcher looks at. */
export type ShortcutEvent = Pick<KeyboardEvent, "key" | "ctrlKey" | "shiftKey" | "altKey">;

const KEY_LABELS: Record<string, string> = {
  arrowdown: "↓",
  arrowup: "↑",
  arrowleft: "←",
  arrowright: "→",
  " ": "Space",
  contextmenu: "Menu",
};

function keyLabel(key: string): string {
  const label = KEY_LABELS[key.toLowerCase()];
  if (label) return label;
  return key.length === 1 ? key.toUpperCase() : key;
}

/**
 * Render a binding the way the shortcuts table displays it. Only the
 * modifiers the spec *requires* are listed, so the text never promises more
 * than the matcher enforces.
 */
export function formatShortcut(spec: ShortcutSpec): string {
  const parts: string[] = [];
  if (spec.ctrl) parts.push("Ctrl");
  if (spec.shift) parts.push("Shift");
  if (spec.alt) parts.push("Alt");
  parts.push(keyLabel(spec.key));
  return parts.join(" + ");
}

/** Render a command's bindings, alternatives joined with "or". */
export function formatKeys(keys: ShortcutSpec[] | undefined): string {
  return (keys ?? []).map(formatShortcut).join(" or ");
}

/** True when *event* satisfies *spec* under the tri-state modifier rules. */
export function matchesShortcut(event: ShortcutEvent, spec: ShortcutSpec): boolean {
  const accepts = (wanted: boolean | undefined, actual: boolean): boolean =>
    wanted === undefined || wanted === actual;
  return (
    event.key.toLowerCase() === spec.key.toLowerCase() &&
    accepts(spec.ctrl, event.ctrlKey) &&
    accepts(spec.shift, event.shiftKey) &&
    accepts(spec.alt, event.altKey)
  );
}

/**
 * The first enabled command in list order whose binding matches *event* —
 * the rule the global key handler dispatches by. *filter* selects the
 * commands eligible for the current phase (e.g. focus helpers that run
 * before the target guards).
 */
export function findCommand(
  commands: Command[],
  event: ShortcutEvent,
  filter: (command: Command) => boolean = () => true,
): Command | undefined {
  return commands.find(
    (command) =>
      filter(command) &&
      command.enabled &&
      command.keys?.some((spec) => matchesShortcut(event, spec)),
  );
}

/**
 * Score how well *query* matches *text* (case-insensitive), or `null` when
 * it does not match. Every whitespace-separated term must appear as a
 * subsequence of the text; word-start, prefix and consecutive characters
 * score higher, gaps and late starts lower.
 */
export function fuzzyScore(text: string, query: string): number | null {
  const haystack = text.toLowerCase();
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return 0;

  let total = 0;
  for (const term of terms) {
    const score = scoreTerm(haystack, term);
    if (score === null) return null;
    total += score;
  }
  return total;
}

// Scoring constants of `scoreTerm`.
const LITERAL_PREFIX_BONUS = 20;
const LITERAL_SUBSTRING_BONUS = 10;
const WORD_START_BONUS = 8;
const CONSECUTIVE_BONUS = 4;
/** The longest gap (in characters) that still costs; beyond it the penalty saturates. */
const MAX_GAP_PENALTY = 10;
const NO_MATCH = Number.NEGATIVE_INFINITY;

/**
 * Score the BEST way *term* occurs in *text* as a subsequence, or `null` when
 * it does not occur.
 *
 * "Best" matters: a greedy leftmost alignment binds each query character to
 * its earliest occurrence, so for "theme" the "t" latched onto the one in
 * "swi**t**ch" and never saw the word-start run in "theme" — the theme
 * command then ranked below "camera barcode scanner" for its own name. This
 * is a small dynamic program instead: `row[j]` is the best score of matching
 * the first `j` characters of the term with the term's j-th character at the
 * current text position, built over the text left to right.
 */
function scoreTerm(text: string, term: string): number | null {
  let score = 0;
  const literal = text.indexOf(term);
  if (literal === 0) score += LITERAL_PREFIX_BONUS;
  else if (literal > 0) score += LITERAL_SUBSTRING_BONUS;

  const length = term.length;
  // best[j] / near[j]: the best score of term[0..j) ending at an earlier
  // position — `near` includes that position, so a gap can be costed exactly.
  const best = new Array<number>(length + 1).fill(NO_MATCH);
  const near = new Array<number>(length + 1).fill(NO_MATCH);
  let previousRow = new Array<number>(length + 1).fill(NO_MATCH);

  for (let i = 0; i < text.length; i++) {
    const row = new Array<number>(length + 1).fill(NO_MATCH);
    const wordStart = i === 0 || !/[a-z0-9]/.test(text[i - 1]);
    // A first character matched late is a weaker match — but far less so
    // than a gap between matched characters, or it would cancel the
    // word-start bonus ("the config editor" vs "scan").
    const startBonus = (wordStart ? WORD_START_BONUS : 0) - Math.min(i, 20) * 0.25;

    if (text[i] === term[0]) row[1] = startBonus;

    for (let j = 2; j <= length; j++) {
      if (text[i] !== term[j - 1]) continue;
      let candidate = NO_MATCH;
      if (best[j - 1] !== NO_MATCH) candidate = best[j - 1] - MAX_GAP_PENALTY;
      if (near[j - 1] !== NO_MATCH) candidate = Math.max(candidate, near[j - 1] - i);
      if (previousRow[j - 1] !== NO_MATCH) {
        candidate = Math.max(candidate, previousRow[j - 1] + CONSECUTIVE_BONUS);
      }
      if (candidate !== NO_MATCH) row[j] = candidate + (wordStart ? WORD_START_BONUS : 0);
    }

    for (let j = 1; j <= length; j++) {
      if (row[j] === NO_MATCH) continue;
      best[j] = Math.max(best[j], row[j]);
      near[j] = Math.max(near[j], row[j] + i + 1);
    }
    previousRow = row;
  }

  return best[length] === NO_MATCH ? null : score + best[length];
}

/** How well *query* fits a command — its title and keywords. */
export function commandScore(command: Command, query: string): number | null {
  return fuzzyScore([command.title, ...(command.keywords ?? [])].join(" "), query);
}

/**
 * How well *query* fits a file. The name matches fuzzily; the relative path
 * only as a literal substring — a path is long enough that a fuzzy
 * subsequence turns almost any query into a match ("readme" against
 * "…/annotated_doc-0.0.7.dist-info").
 */
export function fileScore(
  file: Pick<ScannedFileItem, "filename" | "rel_path">,
  query: string,
): number | null {
  const byName = fuzzyScore(file.filename, query);
  const byPath = file.rel_path.toLowerCase().includes(query.trim().toLowerCase())
    ? fuzzyScore(file.rel_path, query)
    : null;
  const scores = [byName, byPath].filter((score): score is number => score !== null);
  return scores.length ? Math.max(...scores) : null;
}

/**
 * The palette commands matching *query*, best first — recency then registry
 * order breaking score ties. An empty query returns every palette command in
 * registry order. Disabled commands are kept: the palette shows them dimmed
 * with their reason rather than hiding them.
 */
export function rankCommands(
  commands: Command[],
  query: string,
  recentIds: readonly string[] = [],
  limit = Number.POSITIVE_INFINITY,
): Command[] {
  const pool = commands.filter((command) => command.palette !== false);
  const trimmed = query.trim();
  if (!trimmed) return pool.slice(0, limit);

  const recencyOf = (id: string): number =>
    recentIds.indexOf(id) === -1 ? recentIds.length : recentIds.indexOf(id);

  return pool
    .map((command, index) => ({
      command,
      index,
      score: commandScore(command, trimmed),
    }))
    .filter((entry): entry is { command: Command; index: number; score: number } => entry.score !== null)
    .sort(
      (a, b) =>
        b.score - a.score ||
        recencyOf(a.command.id) - recencyOf(b.command.id) ||
        a.index - b.index,
    )
    .slice(0, limit)
    .map((entry) => entry.command);
}

/**
 * The loaded files matching *query*, best first — so `result[0]` is the
 * best match. Quick-open only: an empty query returns nothing (the list
 * itself is the unfiltered view).
 */
export function rankFiles<T extends Pick<ScannedFileItem, "filename" | "rel_path">>(
  files: T[],
  query: string,
  limit = 8,
): T[] {
  const trimmed = query.trim();
  if (!trimmed) return [];

  return files
    .map((file, index) => ({ file, index, score: fileScore(file, trimmed) }))
    .filter((entry): entry is { file: T; index: number; score: number } => entry.score !== null)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .slice(0, limit)
    .map((entry) => entry.file);
}

/**
 * Where the keyboard-invoked context menu opens for *rowIndex*: 24px inside
 * the row's top-left corner, vertically centered on it. Falls back to the
 * viewport corner when the row is virtualized out of the DOM.
 */
export function rowAnchorPoint(rowIndex: number): { x: number; y: number } {
  const rect = document
    .querySelector<HTMLElement>(`[data-row-index="${rowIndex}"]`)
    ?.getBoundingClientRect();
  if (!rect) return { x: 24, y: 24 };
  return { x: rect.left + 24, y: rect.top + rect.height / 2 };
}
