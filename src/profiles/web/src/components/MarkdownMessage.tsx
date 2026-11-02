import ReactMarkdown, { type Components } from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

/**
 * ProFiles messages carry literal escape sequences (a YAML double-quoted
 * scalar keeps `\n` as two characters); unescape them before parsing so the
 * web output matches what the core renderer produces. Same pass and order
 * as `profiles.core.environment.render.render_text`.
 */
function unescapeMessageText(text: string): string {
  return text
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, "\\");
}

/**
 * Themed element mapping. Markdown headings render as h3-h5: the modal title
 * is the page's h2, so a message's `#` must not introduce a competing h1/h2.
 * Code spans keep the inline-chip look; `pre` neutralizes it for fenced
 * blocks (language-tagged or not). Raw HTML is never rendered (no
 * rehype-raw) and link/image URLs pass react-markdown's default sanitizer.
 */
const markdownComponents: Components = {
  h1: ({ children }) => (
    <h3 className="mt-3 mb-1.5 text-base font-bold text-ink first:mt-0">{children}</h3>
  ),
  h2: ({ children }) => (
    <h4 className="mt-3 mb-1 text-sm font-semibold text-ink first:mt-0">{children}</h4>
  ),
  h3: ({ children }) => (
    <h5 className="mt-2 mb-1 text-xs font-semibold text-ink first:mt-0">{children}</h5>
  ),
  p: ({ children }) => (
    <p className="my-1.5 leading-relaxed first:mt-0 last:mb-0">{children}</p>
  ),
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  em: ({ children }) => <em className="italic text-ink-secondary">{children}</em>,
  del: ({ children }) => <del className="text-ink-muted line-through">{children}</del>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-chip-indigo-text underline underline-offset-2 hover:text-ink"
    >
      {children}
    </a>
  ),
  code: ({ children, className }) => (
    <code
      className={`break-words rounded bg-elevated px-1 py-0.5 font-mono text-chip-indigo-text whitespace-pre-wrap ${className ?? ""}`}
    >
      {children}
    </code>
  ),
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg border border-line bg-elevated p-3 font-mono text-xs text-ink [&_code]:bg-transparent [&_code]:px-0 [&_code]:py-0 [&_code]:text-inherit">
      {children}
    </pre>
  ),
  ul: ({ children }) => <ul className="my-1.5 list-disc space-y-0.5 pl-5">{children}</ul>,
  ol: ({ children }) => <ol className="my-1.5 list-decimal space-y-0.5 pl-5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-line-strong pl-3 text-ink-secondary italic">
      {children}
    </blockquote>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-line bg-elevated px-2 py-1 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => <td className="border border-line px-2 py-1 align-top">{children}</td>,
  hr: () => <hr className="my-3 border-line" />,
  img: ({ alt, src, title }) => (
    <img
      src={src}
      alt={alt}
      title={title}
      loading="lazy"
      referrerPolicy="no-referrer"
      className="my-2 max-w-full rounded-lg border border-line"
    />
  ),
};

/**
 * Render a workflow `message:` (or similar user-authored text) as
 * GitHub-flavored Markdown. Single newlines become line breaks
 * (remark-breaks), preserving the line-per-`\n` behavior of the legacy
 * subset renderer.
 */
export function MarkdownMessage({ text }: { text: string }) {
  if (!text) return null;
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]} components={markdownComponents}>
      {unescapeMessageText(text)}
    </ReactMarkdown>
  );
}
