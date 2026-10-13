import React from "react";

type TooltipProps = {
  text: string;
  children: React.ReactNode;
};

const Tooltip: React.FC<TooltipProps> = ({ text, children }) => {
  return (
    <div className="group relative inline-block">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute left-1/2 z-50 mt-2 w-max max-w-64 -translate-x-1/2 rounded-md border border-line bg-elevated px-2 py-1 text-center text-[11px] leading-relaxed text-ink shadow-lg opacity-0 transition-opacity duration-150 group-hover:visible group-hover:opacity-100"
      >
        {text}
        <span className="absolute -top-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 border-l border-t border-line bg-elevated" />
      </span>
    </div>
  );
};

export default Tooltip;