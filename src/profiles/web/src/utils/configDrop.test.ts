import { describe, expect, it } from "vitest";

import {
  isAcceptedConfigName,
  nextDragState,
  pickConfigFile,
  resetDragState,
  type DragTrackerState,
} from "./configDrop";

describe("isAcceptedConfigName", () => {
  it.each(["my.profiles", ".profiles", "prod.profiles.yaml", "data.yml", "config.yaml"])(
    "accepts %s",
    (name) => {
      expect(isAcceptedConfigName(name)).toBe(true);
    },
  );

  it("accepts suffixes case-insensitively", () => {
    expect(isAcceptedConfigName("MY.PROFILES")).toBe(true);
    expect(isAcceptedConfigName("Config.YAML")).toBe(true);
  });

  it.each(["notes.txt", "profile", "profiles", "data.json", ""])("rejects %s", (name) => {
    expect(isAcceptedConfigName(name)).toBe(false);
  });
});

describe("pickConfigFile", () => {
  const file = (name: string) => ({ name } as File);

  it("returns the first accepted file", () => {
    const picked = pickConfigFile([file("notes.txt"), file("my.profiles"), file("other.yml")]);
    expect(picked?.name).toBe("my.profiles");
  });

  it("returns null when nothing is accepted", () => {
    expect(pickConfigFile([file("notes.txt"), file("readme.md")])).toBeNull();
  });
});

describe("nextDragState", () => {
  const HIDDEN: DragTrackerState = { depth: 0, overlayVisible: false };

  it("enter with files shows the overlay and counts the depth", () => {
    expect(nextDragState(HIDDEN, "enter", true)).toEqual({ depth: 1, overlayVisible: true });
  });

  it("enter without files leaves state untouched", () => {
    expect(nextDragState(HIDDEN, "enter", false)).toEqual(HIDDEN);
  });

  it("nested enter/leave keeps the overlay until the last leave", () => {
    let state = nextDragState(HIDDEN, "enter", true);
    state = nextDragState(state, "enter", true);
    expect(state).toEqual({ depth: 2, overlayVisible: true });
    state = nextDragState(state, "leave", false);
    expect(state).toEqual({ depth: 1, overlayVisible: true });
    state = nextDragState(state, "leave", false);
    expect(state).toEqual({ depth: 0, overlayVisible: false });
  });

  it("leave at depth 0 stays hidden", () => {
    expect(nextDragState(HIDDEN, "leave", false)).toEqual(HIDDEN);
  });

  it("drop resets depth and hides", () => {
    const state: DragTrackerState = { depth: 3, overlayVisible: true };
    expect(nextDragState(state, "drop", true)).toEqual(HIDDEN);
  });
});

describe("resetDragState", () => {
  it("returns the hidden zero-depth state", () => {
    expect(resetDragState()).toEqual({ depth: 0, overlayVisible: false });
  });
});
