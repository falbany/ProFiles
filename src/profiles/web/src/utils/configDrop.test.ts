import { describe, expect, it } from "vitest";

import { isAcceptedConfigName, pickConfigFile } from "./configDrop";

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
