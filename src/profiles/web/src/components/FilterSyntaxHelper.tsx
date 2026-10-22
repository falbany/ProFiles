import { describeQuery } from "../utils/searchSyntax";

interface FilterSyntaxHelperProps {
  /** Current filter input value. */
  query: string;
  /** Whether the helper popover is shown (input focused + non-empty query). */
  visible: boolean;
}

/**
 * Live "how my filter reads" feedback under the filter combobox.
 *
 * Purely informational: the popover never captures pointer events, so the combobox
 * dropdown underneath stays fully interactive even while the helper overlaps it.
 */
export function FilterSyntaxHelper({ query, visible }: FilterSyntaxHelperProps) {
  if (!visible) return null;

  const description = describeQuery(query);

  if (description.error) {
    return (
      <div
        data-testid="filter-syntax-helper"
        className="pointer-events-none absolute left-0 right-0 top-full z-[70] mt-1 rounded-md border border-rose-500/30 bg-surface-strong px-3 py-2 text-[11px] leading-5 text-rose-300/90 shadow-xl"
      >
        {description.error}
      </div>
    );
  }

  if (description.groups.length === 0) return null;

  return (
    <div
      data-testid="filter-syntax-helper"
      className="pointer-events-none absolute left-0 right-0 top-full z-[70] mt-1 rounded-md border border-line bg-surface-strong px-3 py-2 text-[11px] leading-5 text-ink-secondary shadow-xl"
    >
      <span className="mr-1.5 align-[1px] text-[10px] uppercase tracking-wide text-ink-muted">
        reads as
      </span>
      {description.groups.map((group, gi) => (
        <span key={gi} data-testid="filter-syntax-group">
          {gi > 0 && <span className="mx-1 font-mono text-indigo-300/80">OR</span>}
          {group.includes.map((term, ti) => (
            <span key={`i-${ti}`}>
              {ti > 0 && <span className="text-ink-muted"> · </span>}
              <span className="font-mono text-indigo-300">{term}</span>
            </span>
          ))}
          {group.includes.length > 0 && group.excludes.length > 0 && (
            <span className="text-ink-muted"> · </span>
          )}
          {group.excludes.map((term, xi) => (
            <span key={`x-${xi}`}>
              {xi > 0 && <span className="text-ink-muted"> · </span>}
              <span className="text-ink-muted">✕ </span>
              <span className="font-mono text-rose-300/70 line-through">{term}</span>
            </span>
          ))}
        </span>
      ))}
    </div>
  );
}
