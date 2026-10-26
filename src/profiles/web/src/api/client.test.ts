import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { reloadConfig } from "./client";

const SAMPLE_CONFIG = {
  title: "Fresh From Disk",
  release: "",
  search_dir: "",
  recursive_search: true,
  theme: "light",
  directories: ["C:/tmp"],
  extensions: [".newext"],
  filters: [],
  active_directory: "C:/tmp",
  config_path: "C:/tmp/.profiles",
  config_exists: true,
  column_headers: ["File"],
  column_names: ["File"],
  row_colors: [],
  reloaded: true,
};

describe("reloadConfig", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify(SAMPLE_CONFIG), { status: 200 }),
      ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs to /api/config/reload and returns the parsed payload", async () => {
    const cfg = await reloadConfig();

    expect(fetch).toHaveBeenCalledWith("/api/config/reload", { method: "POST" });
    expect(cfg.title).toBe("Fresh From Disk");
    expect(cfg.reloaded).toBe(true);
  });

  it("surfaces the server detail message on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            detail: "Invalid dropped configuration (.profiles): unexpected token",
          }),
          { status: 400 },
        ),
      ),
    );

    await expect(reloadConfig()).rejects.toThrow("Invalid dropped configuration");
    expect(fetch).toHaveBeenCalledWith("/api/config/reload", { method: "POST" });
  });
});
