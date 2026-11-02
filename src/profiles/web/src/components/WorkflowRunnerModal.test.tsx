import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WorkflowRunnerModal } from "./WorkflowRunnerModal";

describe("WorkflowRunnerModal layout", () => {
  it("renders nothing when closed", () => {
    const html = renderToStaticMarkup(
      <WorkflowRunnerModal
        isOpen={false}
        onClose={() => {}}
        directory="/tmp"
        filename="app.exe"
      />,
    );
    expect(html).toBe("");
  });

  it("pins the footer outside the scrollable right-column content wrapper", () => {
    const html = renderToStaticMarkup(
      <WorkflowRunnerModal
        isOpen={true}
        onClose={() => {}}
        directory="/tmp"
        filename="app.exe"
      />,
    );

    // Right column itself is a non-scrolling flex column container
    expect(html).toContain('class="flex-1 flex flex-col bg-app"');
    expect(html).not.toContain('class="flex-1 flex flex-col bg-app overflow-y-auto');

    // Inner content area is the scroll container with min-h-0
    const scrollIdx = html.indexOf('class="flex-1 overflow-y-auto p-6 min-h-0"');
    const footerIdx = html.indexOf(
      'class="shrink-0 px-6 pb-4 pt-4 border-t border-line flex items-center justify-between bg-app"',
    );
    expect(scrollIdx).toBeGreaterThan(-1);
    expect(footerIdx).toBeGreaterThan(scrollIdx);

    // Left steps sidebar retains its independent scroll container
    expect(html).toContain(
      'class="w-80 border-r border-line bg-surface-strong/20 p-4 overflow-y-auto flex flex-col gap-2 shrink-0"',
    );
  });
});
