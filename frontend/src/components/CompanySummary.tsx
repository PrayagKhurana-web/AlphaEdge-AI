"use client";

import { useState } from "react";

type CompanySummaryProps = {
  summary: string;
  collapsedHeightClassName?: string;
};

export default function CompanySummary({
  summary,
  collapsedHeightClassName = "max-h-48",
}: CompanySummaryProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div>
      <div
        className={[
          "overflow-hidden text-sm leading-7 text-zinc-300 transition-[max-height] duration-300",
          isExpanded ? "max-h-[1200px]" : collapsedHeightClassName,
        ].join(" ")}
      >
        {summary}
      </div>

      <button
        type="button"
        onClick={() => setIsExpanded((currentValue) => !currentValue)}
        className="mt-4 text-sm font-medium text-blue-400 transition hover:text-blue-300"
      >
        {isExpanded ? "Show less" : "Read more"}
      </button>
    </div>
  );
}