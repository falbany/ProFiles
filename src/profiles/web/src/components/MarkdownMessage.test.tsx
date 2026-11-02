// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MarkdownMessage } from "./MarkdownMessage";

afterEach(() => {
  cleanup();
  document.body.innerHTML = "";
});

describe("MarkdownMessage", () => {
  it("renders headings below the modal title level (# → h3) with inline formatting", () => {
    render(<MarkdownMessage text={"# Launching\\n## Sub"} />);

    const h = screen.getByRole("heading", { level: 3 });
    expect(h.textContent).toBe("Launching");
    expect(screen.getByRole("heading", { level: 4 }).textContent).toBe("Sub");
  });

  it("renders bold, italic and inline code", () => {
    render(<MarkdownMessage text={"**Important** and *note* `cmd.exe`"} />);

    expect(screen.getByText("Important").tagName).toBe("STRONG");
    expect(screen.getByText("note").tagName).toBe("EM");
    const code = screen.getByText("cmd.exe");
    expect(code.tagName).toBe("CODE");
  });

  it("unescapes \\n escapes and honors real single newlines as line breaks", () => {
    const { container } = render(
      <MarkdownMessage text={"Line A\\nLine B\nLine C"} />,
    );

    const paragraph = container.querySelector("p")!;
    expect(paragraph.textContent).toContain("Line A");
    // remark-breaks: soft line breaks render as <br> (line-per-\n contract).
    expect(paragraph.querySelectorAll("br").length).toBeGreaterThanOrEqual(2);
  });

  it("renders GFM tables", () => {
    render(<MarkdownMessage text={"| a | b |\\n| --- | --- |\\n| 1 | 2 |"} />);

    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "a" })).toBeTruthy();
    expect(containerCellCount()).toBe(2);
  });

  it("renders fenced code blocks without the inline chip styling", () => {
    const { container } = render(
      <MarkdownMessage text={"```\nbuild --release\n```"} />,
    );

    const pre = container.querySelector("pre");
    expect(pre).toBeTruthy();
    expect(pre!.querySelector("code")).toBeTruthy();
  });

  it("renders links that open safely in a new context", () => {
    render(<MarkdownMessage text={"[docs](https://example.com)"} />);

    const link = screen.getByRole("link", { name: "docs" });
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("never renders raw HTML (tags surface as escaped text)", () => {
    const { container } = render(
      <MarkdownMessage text={"<img src=x onerror=alert(1)>after"} />,
    );

    expect(document.querySelector("img")).toBeNull();
    expect(container.querySelector("p")!.textContent).toContain("after");
    expect(container.innerHTML).toContain("&lt;img");
  });
});

function containerCellCount(): number {
  return document.querySelectorAll("td").length;
}
