import { describe, expect, it } from "vitest";

import { shortVersion } from "./version";

describe("shortVersion", () => {
  it("strips the dev and local segments from a hatch-vcs version", () => {
    expect(shortVersion("0.12.0b1.dev35+gc05201dfa.d20261115")).toBe("0.12.0b1");
  });

  it("strips the dev segment without a local part", () => {
    expect(shortVersion("0.12.0b1.dev35")).toBe("0.12.0b1");
  });

  it("strips a local segment without a dev part", () => {
    expect(shortVersion("0.12.0+gc05201dfa")).toBe("0.12.0");
  });

  it("passes a clean release version through", () => {
    expect(shortVersion("0.12.0b1")).toBe("0.12.0b1");
    expect(shortVersion("1.2.3")).toBe("1.2.3");
  });

  it("strips a post release segment", () => {
    expect(shortVersion("1.2.3.post1+gabc")).toBe("1.2.3");
  });

  it("returns an empty string for an empty input", () => {
    expect(shortVersion("")).toBe("");
  });
});
