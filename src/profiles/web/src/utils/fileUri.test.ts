import { describe, expect, it } from "vitest";

import { pathToFileUri } from "./fileUri";

describe("pathToFileUri", () => {
  it.each([
    {
      path: "C:\\a\\b.txt",
      expected: "file:///C:/a/b.txt",
      because: "normalizes Windows backslashes to forward slashes",
    },
    {
      path: "C:/a/b.txt",
      expected: "file:///C:/a/b.txt",
      because: "maps a drive path to file:/// with the drive preserved",
    },
    {
      path: "\\\\server\\share\\a.txt",
      expected: "file://server/share/a.txt",
      because: "maps a backslash UNC path to file://host/share",
    },
    {
      path: "//server/share/a.txt",
      expected: "file://server/share/a.txt",
      because: "treats forward-slash UNC the same as backslash UNC",
    },
    {
      path: "/home/u/a.txt",
      expected: "file:///home/u/a.txt",
      because: "maps a POSIX absolute path without doubling the slash",
    },
    {
      path: "C:/dir with space/a.txt",
      expected: "file:///C:/dir%20with%20space/a.txt",
      because: "percent-encodes spaces in path segments",
    },
    {
      path: "C:/rép/a.txt",
      expected: "file:///C:/r%C3%A9p/a.txt",
      because: "percent-encodes non-ASCII characters as UTF-8",
    },
    {
      path: "C:/a#b.txt",
      expected: "file:///C:/a%23b.txt",
      because: "encodes # so it stays path data, not a fragment delimiter",
    },
    {
      path: "C:/a?b.txt",
      expected: "file:///C:/a%3Fb.txt",
      because: "encodes ? so it stays path data, not a query delimiter",
    },
  ])(
    "($path) -> $expected — $because",
    ({ path, expected }) => {
      expect(pathToFileUri(path)).toBe(expected);
    },
  );
});
