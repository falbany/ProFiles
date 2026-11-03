import { Copy } from "lucide-react";

interface CopyableUrlProps {
  url: string;
  /** Accessible name for the copy button; defaults to `Copy <url>`. */
  label?: string;
  /** Extra classes for the row (e.g. spacing inside a dialog body). */
  className?: string;
  /** Called after the URL landed in the clipboard. */
  onCopied?: (url: string) => void;
  /** Called when the clipboard write failed. */
  onCopyError?: (url: string) => void;
}

/**
 * A monospace URL with an icon-only copy button — used in the LAN confirm
 * dialog so the operator can paste the exact address to share.
 */
export function CopyableUrl({
  url,
  label,
  className = "",
  onCopied,
  onCopyError,
}: CopyableUrlProps) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      onCopied?.(url);
    } catch {
      onCopyError?.(url);
    }
  };
  return (
    <span className={`flex items-center justify-between gap-2 ${className}`.trim()}>
      <code className="truncate font-mono text-[11px] text-ink">{url}</code>
      <button
        type="button"
        onClick={copy}
        aria-label={label ?? `Copy ${url}`}
        title={label ?? "Copy"}
        className="focus-ring shrink-0 rounded p-1 text-ink-faint transition-colors hover:bg-elevated hover:text-ink"
      >
        <Copy className="h-3.5 w-3.5" />
      </button>
    </span>
  );
}
