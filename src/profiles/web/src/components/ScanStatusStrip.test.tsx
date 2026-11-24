// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ScanStatusStrip } from "./ScanStatusStrip";

afterEach(cleanup);

describe("ScanStatusStrip", () => {
  it("renders the live count when the server is scanning", () => {
    render(<ScanStatusStrip directory="/mnt/share/programs" progress={1234} inProgress />);

    expect(screen.getByTestId("scan-progress-count").textContent).toBe(
      `${(1234).toLocaleString()} files`,
    );
  });

  it("renders elapsed-only when no progress data exists yet", () => {
    render(<ScanStatusStrip directory="/mnt/share/programs" progress={null} inProgress />);

    expect(screen.queryByTestId("scan-progress-count")).toBeNull();
    expect(screen.getByTestId("scan-status-strip").textContent).toContain("Scanning");
    expect(screen.getByTestId("scan-status-strip").textContent).toContain("programs");
  });

  it("hides the count when the server is not scanning (sort reload)", () => {
    render(<ScanStatusStrip directory="/mnt/share/programs" progress={1234} inProgress={false} />);

    // A stale count must never masquerade as progress while only the
    // client-side spinner runs (no server scan behind a sort reload).
    expect(screen.queryByTestId("scan-progress-count")).toBeNull();
  });
});
