import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { decodeBarcodeImage, exportCsvToDisk, fetchNotifications, reloadConfig } from "./client";

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
