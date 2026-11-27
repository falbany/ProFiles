// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
    watchActive: false,
    watchDisabled: false,
    watchLabel: null as string | null,
    onWatchToggle: vi.fn(),
  };
}

describe("SearchBar base grammar", () => {
  it("repeats the base grammar rows in both tooltips", () => {
    render(<SearchBar {...baseProps()} />);

    // Both bubbles (they portal into document.body) carry the base
    // grammar — those operators are valid in the filter AND the Ext field.
    expect(screen.getAllByText("Supported operators")).toHaveLength(2);
    expect(screen.getAllByText(/either term/)).toHaveLength(2);
    expect(screen.getAllByText(/force include/)).toHaveLength(2);
    expect(screen.getAllByText(/exact phrase/)).toHaveLength(2);
  });
});

describe("SearchBar attribute operators", () => {
  it("advertises attribute operators only in the filter tooltip", () => {
    render(<SearchBar {...baseProps()} />);

    // The Ext combobox does not support attribute operators, so its bubble
    // must NOT carry the File-attributes section: each attribute row is
    // unique in the document while base rows appear in both bubbles.
    const attributeOperators = [
      "size:>10mb",
      "size:1kb..1mb",
      "modified:<7d",
      "modified:>2026-11-01",
      "modified:today",
      "created:>2026-11-01",
      "created:<7d",
    ];
    for (const operator of attributeOperators) {
      expect(screen.getAllByText(operator)).toHaveLength(1);
    }
    // Pin the em-dash descriptions: wordings shared by modified:/created:
    // appear once per family, unique ones exactly once.
    expect(screen.getAllByText(/larger than/)).toHaveLength(1);
    expect(screen.getAllByText(/size range/)).toHaveLength(1);
    expect(screen.getAllByText(/today only/)).toHaveLength(1);
    expect(screen.getAllByText(/after a date/)).toHaveLength(2);
    expect(screen.getAllByText(/within the last 7 days/)).toHaveLength(2);
  });

  it("documents the created operators in the filter tooltip", () => {
    render(<SearchBar {...baseProps()} />);

    // created: mirrors modified: — calendar-date and duration forms.
    expect(screen.getAllByText("created:>2026-11-01")).toHaveLength(1);
    expect(screen.getAllByText("created:<7d")).toHaveLength(1);
  });

  it("advertises the attribute operators in the filter placeholder", () => {
    render(<SearchBar {...baseProps()} />);

    const filterInput = screen.getByPlaceholderText(/size:>10mb/);
    expect(filterInput.getAttribute("placeholder")).toBe(
      "Filter files: keyword, size:>10mb, modified:<7d, a OR b, -tag...",
    );
  });
});

describe("SearchBar watch toggle", () => {
  it("test_watch_toggle_renders_and_calls_on_watch_toggle", () => {
    const props = baseProps();
    render(<SearchBar {...props} />);

    const button = screen.getByRole("button", { name: "Enable watch mode" });
    fireEvent.click(button);
    expect(props.onWatchToggle).toHaveBeenCalledTimes(1);
  });

  it("test_watch_toggle_disabled_while_scanning", () => {
    render(<SearchBar {...baseProps()} scanning watchDisabled />);

    const button = screen.getByRole("button", { name: "Enable watch mode" });
    expect(button).toBeDisabled();
  });

  it("test_watch_toggle_active_style_and_cadence_label", () => {
    render(<SearchBar {...baseProps()} watchActive watchLabel="2s" />);

    const button = screen.getByRole("button", { name: "Disable watch mode" });
    expect(button).toBeEnabled();
    // Active chip styling, exactly like the Timer button's active state.
    expect(button.className).toContain("bg-chip-indigo-bg");
    // The Eye icon pulses while watching.
    expect(button.querySelector(".animate-pulse")).not.toBeNull();
    // The tooltip advertises the cadence from the feed.
    const bubbles = screen.getAllByText(/every 2s/);
    expect(bubbles.length).toBeGreaterThan(0);
    expect(bubbles[0].textContent).toContain("Watching · every 2s");
  });
});
