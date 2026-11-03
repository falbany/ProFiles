// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CopyableUrl } from "./CopyableUrl";

afterEach(() => cleanup());

describe("CopyableUrl", () => {
  it("renders the URL and a labelled copy button", () => {
    render(<CopyableUrl url="http://st-465:8088" />);
    expect(screen.getByText("http://st-465:8088")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /copy http:\/\/st-465:8088/i })
    ).toBeInTheDocument();
  });

  it("writes the URL to the clipboard and reports success", async () => {
    const onCopied = vi.fn();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<CopyableUrl url="http://172.16.41.65:8088" onCopied={onCopied} />);
    await userEvent.click(
      screen.getByRole("button", { name: /copy http:\/\/172\.16\.41\.65:8088/i })
    );

    expect(writeText).toHaveBeenCalledWith("http://172.16.41.65:8088");
    expect(onCopied).toHaveBeenCalledWith("http://172.16.41.65:8088");
  });

  it("reports a clipboard failure instead of throwing", async () => {
    const onCopied = vi.fn();
    const onCopyError = vi.fn();
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    Object.assign(navigator, { clipboard: { writeText } });

    render(
      <CopyableUrl url="http://st-465:8088" onCopied={onCopied} onCopyError={onCopyError} />
    );
    await userEvent.click(screen.getByRole("button", { name: /copy http/i }));

    expect(onCopyError).toHaveBeenCalledWith("http://st-465:8088");
    expect(onCopied).not.toHaveBeenCalled();
  });

  it("uses the custom label when provided", () => {
    render(<CopyableUrl url="http://st-465:8088" label="Copy hostname URL" />);
    expect(
      screen.getByRole("button", { name: "Copy hostname URL" })
    ).toBeInTheDocument();
  });
});
