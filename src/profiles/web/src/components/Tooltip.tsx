import React from "react";

type TooltipProps = {
  /** Plain text or rich content shown on hover. */
  text: React.ReactNode;
  children: React.ReactElement;
  /** Allow the wrapper to grow with a flex parent (`flex-1`, `w-full`, …). */
  block?: boolean;
};

const Tooltip: React.FC<TooltipProps> = ({ text, children, block = true }) => {
  return (
    <div className={`group relative ${block ? "flex min-w-0 flex-1 items-center" : "inline-flex shrink-0 items-center"}`}>
      {children}
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-50 mb-2 w-max max-w-72 -translate-x-1/2 rounded-md border border-line bg-elevated px-2 py-1 text-left text-[11px] leading-relaxed text-ink shadow-lg opacity-0 transition-opacity duration-150 group-hover:visible group-hover:opacity-100"
      >
        {text}
        <span className="absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 border-b border-r border-line bg-elevated" />
      </span>
    </div>
  );
};

export default Tooltip;