// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ActionBar } from "./ActionBar";
import type { ScanProgress } from "../hooks/useScanProgress";

afterEach(cleanup);

/** Build minimal ActionBar props for each scenario. */
function baseProps() {
  return {
    onExecute: vi.fn(),
    scanning: false,
    hasSelection: false,
    fileCount: 3,
  };
}

describe("ActionBar scan strip gate", () => {
  it("renders the strip while a client scan runs", () => {
    render(<ActionBar {...baseProps()} scanning />);

    expect(screen.getByTestId("scan-status-strip")).toBeTruthy();
  });

  it("renders the strip during the initial load scan", () => {
    render(<ActionBar {...baseProps()} initialScanActive />);

    expect(screen.getByTestId("scan-status-strip")).toBeTruthy();
  });

  it("renders no strip when idle", () => {
    render(<ActionBar {...baseProps()} />);

    expect(screen.queryByTestId("scan-status-strip")).toBeNull();
  });

  it("passes the live progress through to the strip", () => {
    const scanProgress: ScanProgress = { progress: 5, inProgress: true };
    render(<ActionBar {...baseProps()} scanning scanProgress={scanProgress} />);

    expect(screen.getByTestId("scan-progress-count").textContent).toBe(
      `${(5).toLocaleString()} files`,
    );
  });
});
