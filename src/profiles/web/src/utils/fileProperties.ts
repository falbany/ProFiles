import type { FileMetadata } from "../api/types";

/** Human-readable size units, smallest first. */
const SIZE_UNITS = ["Bytes", "KB", "MB", "GB", "TB"];

/**
 * Format a byte count as a human-readable size string ("1.5 KB").
 *
 * Args:
 *   bytes: File size in bytes.
 *
 * Returns:
 *   Size formatted with two decimal places and a unit suffix.
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const i = Math.max(0, Math.min(SIZE_UNITS.length - 1, Math.floor(Math.log(bytes) / Math.log(k))));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + SIZE_UNITS[i];
}

/**
 * Return the parent directory portion of a Windows or POSIX path.
 *
 * Handles both separators; returns "" for a bare filename.
 */
export function parentDirectory(path: string): string {
  const idx = Math.max(path.lastIndexOf("\\"), path.lastIndexOf("/"));
  return idx === -1 ? "" : path.slice(0, idx);
}

/**
 * Build a multi-line plain-text summary of the most useful file properties,
 * suitable for pasting into tickets or QC records.
 */
export function buildPropertiesSummary(metadata: FileMetadata): string {
  const lines: string[] = [
    `File Properties: ${metadata.name}`,
    `Path: ${metadata.path}`,
    `Type: ${metadata.type}`,
    `Size: ${formatFileSize(metadata.size_bytes)}`,
    `Created: ${metadata.created}`,
    `Modified: ${metadata.modified}`,
  ];
  if (metadata.md5) lines.push(`MD5: ${metadata.md5}`);
  if (metadata.sha256) lines.push(`SHA256: ${metadata.sha256}`);
  return lines.join("\n");
}
