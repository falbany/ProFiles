import { describe, expect, it } from "vitest";

import { resolveSessionTheme } from "./theme";

describe("resolveSessionTheme", () => {
  it("maps auto to dark", () => {
    expect(resolveSessionTheme("auto")).toBe("dark");
  });

  it("passes light through", () => {
    expect(resolveSessionTheme("light")).toBe("light");
  });

  it("maps dark to dark", () => {
    expect(resolveSessionTheme("dark")).toBe("dark");
  });

  it("falls back to dark for unknown or missing values", () => {
    expect(resolveSessionTheme("neon-pink")).toBe("dark");
    expect(resolveSessionTheme(undefined)).toBe("dark");
  });
});
