/**
 * Build a `file:` URI from a local filesystem path.
 *
 * Replaces the previous `new URL("file:///").href + path.replace(/\\/g, "/")`
 * construction (App.tsx copy-uri action): because backslashes were normalized
 * before concatenation, a UNC path (`\\server\share\a.txt`) produced
 * `file://///server/share/a.txt` (five leading slashes) and a POSIX path
 * (`/home/u/a.txt`) produced `file:////home/u/a.txt` (four) — both invalid —
 * and spaces, non-ASCII and `#`/`?` were left unencoded. Here a UNC path
 * (`\\host\share\...` or `//host/share/...`) becomes
 * `file://host/share/...`, everything else becomes
 * `file:///` + the path with forward slashes, and path data is
 * percent-encoded (UTF-8) while `/` separators stay intact.
 *
 * @param path - Local path in Windows or POSIX form (UNC supported).
 * @returns The corresponding `file:` URI.
 */
export function pathToFileUri(path: string): string {
  const normalized = path.replace(/\\/g, "/");
  const isUnc = normalized.startsWith("//");
  const body = encodePathData(normalized.replace(/^\/+/, ""));
  return isUnc ? `file://${body}` : `file:///${body}`;
}

/**
 * Hand-rolled encoder instead of `encodeURI` (KISS): encodeURI keeps `#` and
 * `?` as URI delimiters, but here they are path data and must be encoded.
 * Safe chars are RFC 3986 "pchar" (unreserved + sub-delims + `:`/`@`);
 * `/` is handled separately as the separator.
 */
const SEGMENT_SAFE = /[A-Za-z0-9\-._~!$&'()*+,;=:@]/;

function encodePathData(path: string): string {
  return [...path]
    .map((char) =>
      char === "/" || SEGMENT_SAFE.test(char) ? char : percentEncodeUtf8(char),
    )
    .join("");
}

function percentEncodeUtf8(char: string): string {
  return Array.from(new TextEncoder().encode(char), (byte) =>
    `%${byte.toString(16).toUpperCase().padStart(2, "0")}`,
  ).join("");
}
