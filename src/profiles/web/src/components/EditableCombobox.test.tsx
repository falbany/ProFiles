// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { EditableCombobox } from "./EditableCombobox";

function baseProps() {
  return {
    id: "test-combobox",
    ariaLabel: "Test combo",
    options: [".py", ".toml"],
  };
}

beforeEach(() => {
  // jsdom does not implement scrollIntoView (active-option keep-in-view effect).
  Element.prototype.scrollIntoView = vi.fn();
});

afterEach(() => cleanup());

describe("EditableCombobox commitOn=change (default)", () => {
  it("fires onChange on every keystroke", () => {
    const onChange = vi.fn();
    render(<EditableCombobox {...baseProps()} value="" onChange={onChange} />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "a" } });
    fireEvent.change(input, { target: { value: "ab" } });
    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenLastCalledWith("ab");
  });
});

describe("EditableCombobox commitOn=deferred", () => {
  it("keeps keystrokes local and commits on Enter (issue #121)", () => {
    const onChange = vi.fn();
    render(<EditableCombobox {...baseProps()} value="" onChange={onChange} commitOn="deferred" />);
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "/tmp/x" } });
    expect(onChange).not.toHaveBeenCalled();
    expect(input).toHaveValue("/tmp/x");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("/tmp/x");
  });

  it("commits on blur (issue #121)", async () => {
    const onChange = vi.fn();
    render(
      <div>
        <EditableCombobox {...baseProps()} value="" onChange={onChange} commitOn="deferred" />
        <button type="button">elsewhere</button>
      </div>,
    );
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: ".md" } });
    fireEvent.blur(input);
    expect(onChange).toHaveBeenCalledWith(".md");
  });

  it("does not re-commit on blur when nothing changed", async () => {
    const onChange = vi.fn();
    render(<EditableCombobox {...baseProps()} value=".py" onChange={onChange} commitOn="deferred" />);
    fireEvent.blur(screen.getByRole("combobox"));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("commits immediately when an option is picked (issue #121)", () => {
    /** Controlled wrapper so the committed value flows back into the input. */
    function Harness() {
      const [value, setValue] = useState("");
      return (
        <EditableCombobox
          {...baseProps()}
          value={value}
          onChange={setValue}
          commitOn="deferred"
        />
      );
    }
    render(<Harness />);
    const input = screen.getByRole("combobox");
    fireEvent.keyDown(input, { key: "ArrowDown" }); // opens the list
    fireEvent.click(screen.getByRole("option", { name: ".py" }));
    expect(input).toHaveValue(".py");
  });

  it("Enter-select of an option stops propagation (issue #122 stale-closure scan)", () => {
    const onChange = vi.fn();
    const onWindowKeyDown = vi.fn();
    window.addEventListener("keydown", onWindowKeyDown);
    render(<EditableCombobox {...baseProps()} value="" onChange={onChange} commitOn="deferred" />);
    const input = screen.getByRole("combobox");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(".py");
    // Only the ArrowDown may bubble — the Enter was consumed by the combobox.
    const enterEvents = onWindowKeyDown.mock.calls.filter(([e]) => e.key === "Enter");
    expect(enterEvents).toHaveLength(0);
    window.removeEventListener("keydown", onWindowKeyDown);
  });

  it("Enter on an unchanged value bubbles to the window scan shortcut", () => {
    const onChange = vi.fn();
    const onWindowKeyDown = vi.fn();
    window.addEventListener("keydown", onWindowKeyDown);
    render(<EditableCombobox {...baseProps()} value=".py" onChange={onChange} commitOn="deferred" />);
    fireEvent.keyDown(screen.getByRole("combobox"), { key: "Enter" });
    expect(onWindowKeyDown).toHaveBeenCalledTimes(1);
    window.removeEventListener("keydown", onWindowKeyDown);
  });
});
