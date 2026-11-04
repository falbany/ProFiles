import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  decodeBarcodeImage,
  exportCsvToDisk,
  fetchConfigContent,
  fetchConfigTemplate,
  fetchNotifications,
  reloadConfig,
  saveConfigFile,
  saveConfigFileAs,
  validateConfigContent,
} from "./client";

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

describe("fetchNotifications", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("GETs /api/notifications with the after cursor and returns the events", async () => {
    const events = [
      { id: 7, kind: "config_handoff", message: "Configuration applied", config_applied: true },
    ];
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ events }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await fetchNotifications(6);

    expect(fetchMock).toHaveBeenCalledWith("/api/notifications?after=6");
    expect(res.events).toEqual(events);
  });

  it("throws on HTTP failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 500 })),
    );

    await expect(fetchNotifications(0)).rejects.toThrow("Failed to fetch notifications");
  });
});

describe("exportCsvToDisk", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs the CSV content to /api/actions/export-csv and returns the saved path", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ status: "success", message: "CSV exported to /tmp/out.csv", path: "/tmp/out.csv" }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await exportCsvToDisk("name,version\n", "profiles-export-x.csv");

    expect(fetchMock).toHaveBeenCalledWith("/api/actions/export-csv", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: "name,version\n", filename: "profiles-export-x.csv" }),
    });
    expect(res.status).toBe("success");
    expect(res.path).toBe("/tmp/out.csv");
  });

  it("throws on HTTP failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 500 })),
    );

    await expect(exportCsvToDisk("a,b\n", "out.csv")).rejects.toThrow("Failed to export CSV");
  });
});

describe("decodeBarcodeImage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs the base64 frame and formats to /api/actions/barcode/decode", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ decoded: "dir=/tmp;scan=1", format: "QR Code" }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await decodeBarcodeImage({ imageBase64: "QUJD", formats: ["qr_code"] });

    expect(fetchMock).toHaveBeenCalledWith("/api/actions/barcode/decode", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_base64: "QUJD", formats: ["qr_code"] }),
    });
    expect(res.decoded).toBe("dir=/tmp;scan=1");
    expect(res.format).toBe("QR Code");
  });

  it("surfaces the 503 detail as an explicit unavailable error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 503 })),
    );

    await expect(decodeBarcodeImage({ imageBase64: "QUJD" })).rejects.toThrow(
      "Server-side barcode decoding is unavailable",
    );
  });

  it("throws on other HTTP failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 400 })),
    );

    await expect(decodeBarcodeImage({ imageBase64: "QUJD" })).rejects.toThrow("HTTP 400");
  });
});

describe("fetchConfigContent", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("GETs /api/config/content and returns the editor payload", async () => {
    const payload = {
      filename: ".profiles",
      content: "title: Fresh From Disk\n",
      config_path: "/tmp/.profiles",
      session_trial: false,
    };
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(payload), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await fetchConfigContent();

    expect(fetchMock).toHaveBeenCalledWith("/api/config/content");
    expect(res).toEqual(payload);
  });

  it("carries the 404 status when the recorded file was deleted", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: "Configuration file not found: /tmp/.profiles" }),
          { status: 404 },
        ),
      ),
    );

    const err = (await fetchConfigContent().catch((error: unknown) => error)) as ApiError;

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(404);
    expect(err.message).toContain("Configuration file not found");
  });
});

describe("validateConfigContent", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs the filename and content to /api/config/validate and returns the issues", async () => {
    const issues = [{ severity: "error" as const, message: "unexpected token" }];
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ valid: false, issues }), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await validateConfigContent(".profiles", "defaults: [unclosed");

    expect(fetchMock).toHaveBeenCalledWith("/api/config/validate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: ".profiles", content: "defaults: [unclosed" }),
    });
    expect(res.valid).toBe(false);
    expect(res.issues).toEqual(issues);
  });
});

describe("fetchConfigTemplate", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs to /api/config/template and returns the starter content", async () => {
    const template = { content: "# ProFiles — Starter Configuration\ntitle: ...\n", filename: ".profiles" };
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(template), { status: 200 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const res = await fetchConfigTemplate();

    expect(fetchMock).toHaveBeenCalledWith("/api/config/template", { method: "POST" });
    expect(res.content).toBe(template.content);
    expect(res.filename).toBe(".profiles");
  });
});

describe("saveConfigFile", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs the content and force flag to /api/config/save and returns the applied config", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({
          status: "SAVED",
          path: "/tmp/.profiles",
          config: SAMPLE_CONFIG,
          content_hash: "abc123",
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const { config: cfg, contentHash } = await saveConfigFile("title: Fresh From Disk\n", true);

    expect(fetchMock).toHaveBeenCalledWith("/api/config/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: "title: Fresh From Disk\n",
        force: true,
        baseline_hash: null,
        overwrite_changes: false,
      }),
    });
    expect(cfg.title).toBe("Fresh From Disk");
    expect(cfg.config_path).toBe("C:/tmp/.profiles");
    expect(contentHash).toBe("abc123");
  });

  it("sends the staleness baseline and overwrite decision when provided (issue #116)", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ status: "SAVED", path: "/tmp/.profiles", config: SAMPLE_CONFIG }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await saveConfigFile("title: Fresh From Disk\n", false, {
      baselineHash: "deadbeef",
      overwriteChanges: true,
    });

    expect(fetchMock).toHaveBeenCalledWith("/api/config/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: "title: Fresh From Disk\n",
        force: false,
        baseline_hash: "deadbeef",
        overwrite_changes: true,
      }),
    });
  });

  it("surfaces the plain-string detail for a session-trial refusal", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            detail:
              "Cannot save: the active configuration is a session trial with no file on disk. Load or create a configuration first.",
          }),
          { status: 400 },
        ),
      ),
    );

    await expect(saveConfigFile("title: Fresh From Disk\n", false)).rejects.toThrow(
      "Cannot save: the active configuration is a session trial",
    );
  });

  it("keeps the validation issues list intact on a 400", async () => {
    const issues = [
      { severity: "error" as const, message: "title: field required" },
      { severity: "error" as const, message: "unknown field 'directory'" },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: issues }), { status: 400 }),
      ),
    );

    const err = (await saveConfigFile("defaults: [unclosed", false).catch(
      (error: unknown) => error,
    )) as ApiError;

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.detail).toEqual(issues);
    expect(err.message).toBe("Failed to save configuration");
  });
});

describe("saveConfigFileAs", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("POSTs the save-as params to /api/config/save-as and returns the applied config", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ status: "SAVED", path: "/tmp/copy/.profiles", config: SAMPLE_CONFIG }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const cfg = (
      await saveConfigFileAs({
        content: "title: Fresh From Disk\n",
        filename: ".profiles",
        directory: "/tmp/copy",
        force: false,
        overwrite: true,
      })
    ).config;

    expect(fetchMock).toHaveBeenCalledWith("/api/config/save-as", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: "title: Fresh From Disk\n",
        filename: ".profiles",
        directory: "/tmp/copy",
        force: false,
        overwrite: true,
      }),
    });
    expect(cfg.title).toBe("Fresh From Disk");
  });

  it("surfaces the 409 overwrite-guard detail", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            detail:
              "Configuration already exists at /tmp/copy/.profiles. Retry with overwrite=true to replace it.",
          }),
          { status: 409 },
        ),
      ),
    );

    const err = (await saveConfigFileAs({
      content: "title: Fresh From Disk\n",
      filename: ".profiles",
      directory: "/tmp/copy",
      force: false,
      overwrite: false,
    }).catch((error: unknown) => error)) as ApiError;

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.message).toContain("already exists");
  });
});
