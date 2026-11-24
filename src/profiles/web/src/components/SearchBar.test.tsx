// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SearchBar } from "./SearchBar";

afterEach(cleanup);

/** Build minimal SearchBar props for each scenario. */
function baseProps() {
  return {
    extensions: [".py"],
    activeExtension: ".py",
    onExtensionChange: vi.fn(),
    filterText: "",
    onFilterTextChange: vi.fn(),
    recursive: true,
    onRecursiveChange: vi.fn(),
    onScan: vi.fn(),
    scanning: false,
    barcodeMode: false,
    onBarcodeToggle: vi.fn(),
    autoRescanActive: false,
    onTimerClick: vi.fn(),
  };
}

describe("SearchBar attribute operators", () => {
  it("lists the attribute operators in the filter tooltip", () => {
    render(<SearchBar {...baseProps()} />);

    // Both the filter input and the Ext combobox render the same
    // OPERATOR_HELP bubble (portal), so each row appears twice in the DOM.
    const operators = [
      "size:>10mb",
      "size:1kb..1mb",
      "modified:<7d",
      "modified:>2026-11-01",
      "modified:today",
    ];
    for (const operator of operators) {
      expect(screen.getAllByText(operator).length).toBeGreaterThan(0);
    }
    // Pin a few em-dash descriptions so the rows stay meaningful.
    for (const description of [/larger than/, /size range/, /within the last 7 days/, /after a date/, /today only/]) {
      expect(screen.getAllByText(description).length).toBeGreaterThan(0);
    }
  });

  it("advertises the attribute operators in the filter placeholder", () => {
    render(<SearchBar {...baseProps()} />);

    const filterInput = screen.getByPlaceholderText(/size:>10mb/);
    expect(filterInput.getAttribute("placeholder")).toBe(
      "Filter files: keyword, size:>10mb, modified:<7d, a OR b, -tag...",
    );
  });
});
