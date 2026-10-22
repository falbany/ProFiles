import { describe, expect, it } from "vitest";
import type { FileMetadata } from "../api/types";
import { buildPropertiesSummary, formatFileSize, parentDirectory } from "./fileProperties";

describe("formatFileSize", () => {
  it("returns '0 Bytes' for zero", () => {
    expect(formatFileSize(0)).toBe("0 Bytes");
  });

  it("formats byte-sized values without conversion", () => {
    expect(formatFileSize(512)).toBe("512 Bytes");
  });

  it("formats kilobytes", () => {
    expect(formatFileSize(1536)).toBe("1.5 KB");
  });

  it("formats megabytes", () => {
    expect(formatFileSize(5 * 1024 * 1024)).toBe("5 MB");
  });

  it("formats gigabytes", () => {
    expect(formatFileSize(3 * 1024 * 1024 * 1024)).toBe("3 GB");
  });
});

describe("parentDirectory", () => {
  it("extracts the Windows parent directory", () => {
    expect(parentDirectory("C:\\dir\\sub\\file.txt")).toBe("C:\\dir\\sub");
  });

  it("extracts the POSIX parent directory", () => {
    expect(parentDirectory("/usr/bin/app")).toBe("/usr/bin");
  });

  it("returns an empty string for a bare filename", () => {
    expect(parentDirectory("file.txt")).toBe("");
  });
});

describe("buildPropertiesSummary", () => {
  const baseMetadata: FileMetadata = {
    name: "report.xlsx",
    path: "C:\\dir\\report.xlsx",
    size_bytes: 3276800,
    modified: "2026-10-20 10:15:00",
    created: "2026-10-01 08:00:00",
    type: "xlsx",
    md5: "aabbcc",
    sha256: "ddeeff00",
    attributes: { is_file: true },
  };

  it("includes name, path, size, type, and timestamps", () => {
    const summary = buildPropertiesSummary(baseMetadata);
    expect(summary).toContain("File Properties: report.xlsx");
    expect(summary).toContain("Path: C:\\dir\\report.xlsx");
    expect(summary).toContain("Type: xlsx");
    expect(summary).toContain(`Size: ${formatFileSize(3276800)}`);
    expect(summary).toContain("Created: 2026-10-01 08:00:00");
    expect(summary).toContain("Modified: 2026-10-20 10:15:00");
  });

  it("includes hashes when present", () => {
    const summary = buildPropertiesSummary(baseMetadata);
    expect(summary).toContain("MD5: aabbcc");
    expect(summary).toContain("SHA256: ddeeff00");
  });

  it("omits hash lines when hashes are empty", () => {
    const summary = buildPropertiesSummary({
      ...baseMetadata,
      md5: "",
      sha256: "",
    });
    expect(summary).not.toContain("MD5:");
    expect(summary).not.toContain("SHA256:");
  });
});
