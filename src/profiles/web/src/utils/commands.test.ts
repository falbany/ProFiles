// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import {
  findCommand,
  formatKeys,
  formatShortcut,
  fuzzyScore,
  matchesShortcut,
  rankCommands,
  rankFiles,
  rowAnchorPoint,
} from "./commands";
import type { Command } from "./commands";
import type { ScannedFileItem } from "../api/types";

function makeCommand(overrides: Partial<Command> & Pick<Command, "id" | "title">): Command {
  return { group: "view", enabled: true, run: () => {}, ...overrides };
}

function keyEvent(
  key: string,
  mods: { ctrlKey?: boolean; shiftKey?: boolean; altKey?: boolean } = {},
): Pick<KeyboardEvent, "key" | "ctrlKey" | "shiftKey" | "altKey"> {
  return {
    key,
    ctrlKey: mods.ctrlKey ?? false,
    shiftKey: mods.shiftKey ?? false,
    altKey: mods.altKey ?? false,
  };
}

describe("formatShortcut", () => {
  it("lists only the required modifiers, in a fixed order", () => {
    expect(formatShortcut({ key: "r", ctrl: true })).toBe("Ctrl + R");
    expect(formatShortcut({ key: "l", ctrl: true, shift: true })).toBe("Ctrl + Shift + L");
    expect(formatShortcut({ key: "k", ctrl: true, shift: false })).toBe("Ctrl + K");
  });

  it("labels single characters in upper case and keeps punctuation", () => {
    expect(formatShortcut({ key: "p" })).toBe("P");
    expect(formatShortcut({ key: ",", ctrl: true })).toBe("Ctrl + ,");
    expect(formatShortcut({ key: "?" })).toBe("?");
    expect(formatShortcut({ key: "F5" })).toBe("F5");
  });

  it("renders arrows as glyphs and leaves named keys as written", () => {
    expect(formatShortcut({ key: "ArrowDown" })).toBe("↓");
    expect(formatShortcut({ key: "ArrowUp" })).toBe("↑");
    expect(formatShortcut({ key: "PageUp" })).toBe("PageUp");
    expect(formatShortcut({ key: "Enter" })).toBe("Enter");
    expect(formatShortcut({ key: "ContextMenu" })).toBe("Menu");
  });

  it("joins alternative bindings with 'or'", () => {
    expect(formatKeys([{ key: "?" }, { key: "/", ctrl: true }])).toBe("? or Ctrl + /");
    expect(formatKeys(undefined)).toBe("");
  });
});

describe("matchesShortcut", () => {
  // The original keydown handler checked Shift for some bindings (L, K, T, B)
  // and not for others (R, D, E, F, H, comma). `undefined` keeps that exact
  // behaviour; a false/true flag requires the modifier's absence/presence.
  it("ignores a modifier the spec leaves undefined", () => {
    const spec = { key: "r", ctrl: true };
    expect(matchesShortcut(keyEvent("r", { ctrlKey: true }), spec)).toBe(true);
    expect(matchesShortcut(keyEvent("R", { ctrlKey: true, shiftKey: true }), spec)).toBe(true);
  });

  it("requires the modifiers the spec pins", () => {
    const lan = { key: "k", ctrl: true, shift: false };
    expect(matchesShortcut(keyEvent("k", { ctrlKey: true }), lan)).toBe(true);
    expect(matchesShortcut(keyEvent("k", { ctrlKey: true, shiftKey: true }), lan)).toBe(false);
    expect(matchesShortcut(keyEvent("k"), lan)).toBe(false);

    const plain = { key: "p", ctrl: false, shift: false, alt: false };
    expect(matchesShortcut(keyEvent("p"), plain)).toBe(true);
    expect(matchesShortcut(keyEvent("P"), plain)).toBe(true);
    expect(matchesShortcut(keyEvent("p", { ctrlKey: true }), plain)).toBe(false);
    expect(matchesShortcut(keyEvent("p", { shiftKey: true }), plain)).toBe(false);
    expect(matchesShortcut(keyEvent("p", { altKey: true }), plain)).toBe(false);
  });

  it("compares the key case-insensitively and nothing else", () => {
    expect(matchesShortcut(keyEvent("F10", { shiftKey: true }), { key: "f10", shift: true })).toBe(true);
    expect(matchesShortcut(keyEvent("F10"), { key: "f10", shift: true })).toBe(false);
    expect(matchesShortcut(keyEvent("F5", { ctrlKey: true }), { key: "F5" })).toBe(true);
    expect(matchesShortcut(keyEvent("r"), { key: "r", ctrl: true })).toBe(false);
  });
});

describe("findCommand", () => {
  const commands: Command[] = [
    makeCommand({ id: "lan", title: "LAN access", keys: [{ key: "k", ctrl: true, shift: false }] }),
    makeCommand({ id: "log", title: "Log viewer", keys: [{ key: "l", ctrl: true, shift: true }] }),
    makeCommand({ id: "props", title: "Properties", keys: [{ key: "p" }], enabled: false }),
  ];

  it("returns the first ENABLED command bound to the event", () => {
    expect(findCommand(commands, keyEvent("k", { ctrlKey: true }))?.id).toBe("lan");
    expect(findCommand(commands, keyEvent("l", { ctrlKey: true, shiftKey: true }))?.id).toBe("log");
    // Bound but disabled: skipped like an unbound key.
    expect(findCommand(commands, keyEvent("p"))).toBeUndefined();
    // No binding claims Ctrl+Shift+K.
    expect(findCommand(commands, keyEvent("k", { ctrlKey: true, shiftKey: true }))).toBeUndefined();
  });

  it("honours the eligibility filter", () => {
    const early = (command: Command) => command.beforeTargetGuard === true;
    expect(findCommand(commands, keyEvent("l", { ctrlKey: true, shiftKey: true }), early)).toBeUndefined();
    expect(
      findCommand(
        [{ ...commands[1], beforeTargetGuard: true }, commands[0]],
        keyEvent("l", { ctrlKey: true, shiftKey: true }),
        early,
      )?.id,
    ).toBe("log");
  });
});

describe("fuzzyScore", () => {
  it("scores a subsequence match and rejects a non-match", () => {
    expect(fuzzyScore("Copy Full Path", "cfp")).toBeGreaterThan(0);
    expect(fuzzyScore("Copy Full Path", "xyz")).toBeNull();
  });

  it("is case-insensitive and treats an empty query as a neutral match", () => {
    expect(fuzzyScore("Rescan the file list", "RESCAN")).toBeGreaterThan(0);
    expect(fuzzyScore("anything", "")).toBe(0);
    expect(fuzzyScore("anything", "   ")).toBe(0);
  });

  it("prefers word-start matches and tight matches over scattered ones", () => {
    const tight = fuzzyScore("Rescan the file list", "rescan");
    const scattered = fuzzyScore("Turn off recursive scanning", "rescan");
    expect(tight).not.toBeNull();
    expect(scattered).not.toBeNull();
    expect(tight as number).toBeGreaterThan(scattered as number);

    // "c" landing on a word start beats the same letter mid-word.
    const wordStart = fuzzyScore("Open the config editor", "c");
    const midWord = fuzzyScore("Scan the file list", "c");
    expect(wordStart as number).toBeGreaterThan(midWord as number);
  });

  it("requires every whitespace-separated term to match", () => {
    expect(fuzzyScore("Compute SHA-256 hash", "hash sha")).toBeGreaterThan(0);
    expect(fuzzyScore("Compute SHA-256 hash", "hash md5")).toBeNull();
  });

  it("scores the best alignment, not the leftmost one", () => {
    // Regression: a greedy matcher bound the "t" of "theme" to the one in
    // "swi*t*ch", so the theme command ranked below "camera barcode scanner"
    // for its own name — and Enter ran the wrong command.
    const theme = fuzzyScore("Switch theme (dark / light) toggle", "theme");
    const camera = fuzzyScore("Open the camera barcode scanner webcam qr", "theme");
    expect(theme as number).toBeGreaterThan(camera as number);

    // A word-start run beats characters gathered from all over the text.
    const run = fuzzyScore("switch theme", "theme");
    const scattered = fuzzyScore("the time", "theme");
    expect(scattered).not.toBeNull();
    expect(run as number).toBeGreaterThan(scattered as number);
  });

  it("matches acronyms across words", () => {
    expect(fuzzyScore("Open the log viewer", "olv")).toBeGreaterThan(0);
    expect(fuzzyScore("Copy full path", "cfp")).toBeGreaterThan(0);
    expect(fuzzyScore("Open the log viewer", "xyz")).toBeNull();
  });
});

describe("rankCommands", () => {
  const commands: Command[] = [
    makeCommand({ id: "rescan", title: "Rescan the file list" }),
    makeCommand({ id: "copy-path", title: "Copy full path", keywords: ["clipboard"] }),
    makeCommand({ id: "copy-name", title: "Copy file name" }),
    makeCommand({
      id: "delete",
      title: "Delete file",
      keywords: ["remove", "erase"],
      enabled: false,
      disabledReason: "Select a file first",
    }),
    makeCommand({ id: "next", title: "Move to the next file", palette: false }),
  ];

  it("returns every palette command in registry order for an empty query", () => {
    expect(rankCommands(commands, "").map((c) => c.id)).toEqual([
      "rescan",
      "copy-path",
      "copy-name",
      "delete",
    ]);
  });

  it("keeps only the matches, best first", () => {
    expect(rankCommands(commands, "copy").map((c) => c.id)).toEqual(["copy-path", "copy-name"]);
    // "re" fits "Rescan…" tighter than the "remove" keyword of Delete.
    expect(rankCommands(commands, "re").map((c) => c.id)).toEqual(["rescan", "delete"]);
  });

  it("breaks score ties by recency, then registry order", () => {
    // Both copy commands match "copy" with the same shape.
    expect(rankCommands(commands, "copy", ["copy-name"]).map((c) => c.id)).toEqual([
      "copy-name",
      "copy-path",
    ]);
    expect(rankCommands(commands, "copy", ["rescan"]).map((c) => c.id)).toEqual([
      "copy-path",
      "copy-name",
    ]);
  });

  it("ranks the command whose name was typed above incidental matches", () => {
    const catalog = [
      makeCommand({ id: "camera", title: "Open the camera barcode scanner", keywords: ["webcam", "qr"] }),
      makeCommand({ id: "theme", title: "Switch theme (dark / light)", keywords: ["toggle"] }),
    ];
    expect(rankCommands(catalog, "theme").map((c) => c.id)).toEqual(["theme", "camera"]);
    expect(rankCommands(catalog, "theme")[0].id).toBe("theme");
  });

  it("matches keywords and keeps disabled commands visible", () => {
    const [hit] = rankCommands(commands, "remove");
    expect(hit.id).toBe("delete");
    expect(hit.enabled).toBe(false);
  });

  it("never surfaces commands hidden from the palette", () => {
    // "next" only fits the hidden list-navigation command. ("move" would
    // legitimately match Delete through its "remove" keyword.)
    expect(rankCommands(commands, "next")).toEqual([]);
  });

  it("honours the limit", () => {
    expect(rankCommands(commands, "e", [], 1)).toHaveLength(1);
  });
});

describe("rankFiles", () => {
  const files = [
    { filename: "report_a.log", rel_path: "logs/report_a.log", path: "/d/logs/report_a.log" },
    { filename: "readme.md", rel_path: "readme.md", path: "/d/readme.md" },
    { filename: "bench_report.md", rel_path: "bench_report.md", path: "/d/bench_report.md" },
  ] as ScannedFileItem[];

  it("matches the file name fuzzily, but the path only literally", () => {
    // "readme" is a scattered subsequence of this long path — not a match.
    const noise = {
      filename: "METADATA",
      rel_path: "build/app/annotated_doc-0.0.7.dist-info/METADATA",
    } as ScannedFileItem;
    expect(rankFiles([...files, noise], "readme").map((f) => f.filename)).toEqual(["readme.md"]);
    expect(rankFiles([noise], "readme")).toEqual([]);
    // A folder name in the query still finds the files inside it.
    expect(rankFiles(files, "logs/rep").map((f) => f.filename)).toEqual(["report_a.log"]);
  });

  it("returns nothing without a query", () => {
    expect(rankFiles(files, "")).toEqual([]);
  });

  it("matches the file name and the relative path, best first", () => {
    expect(rankFiles(files, "report").map((f) => f.filename)).toEqual([
      "report_a.log",
      "bench_report.md",
    ]);
    expect(rankFiles(files, "logs").map((f) => f.filename)).toEqual(["report_a.log"]);
    expect(rankFiles(files, "zzz")).toEqual([]);
  });
});

describe("rowAnchorPoint", () => {
  it("anchors 24px inside the row's top-left corner", () => {
    const row = document.createElement("div");
    row.setAttribute("data-row-index", "3");
    row.getBoundingClientRect = () =>
      ({ left: 100, top: 50, width: 200, height: 28 }) as DOMRect;
    document.body.appendChild(row);
    expect(rowAnchorPoint(3)).toEqual({ x: 124, y: 64 });
    row.remove();
  });

  it("falls back to the top-left corner when the row is not rendered", () => {
    expect(rowAnchorPoint(7)).toEqual({ x: 24, y: 24 });
  });
});
