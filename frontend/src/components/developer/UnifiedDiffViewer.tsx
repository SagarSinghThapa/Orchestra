"use client";

import React, { useState } from "react";

interface UnifiedDiffViewerProps {
  diff: string;
  path?: string;
}

const LINE_LIMIT = 500;

export function UnifiedDiffViewer({ diff, path }: UnifiedDiffViewerProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const lines = diff.split("\n");
  const isCapped = lines.length > LINE_LIMIT;
  const displayedLines = isCapped && !isExpanded ? lines.slice(0, LINE_LIMIT) : lines;

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-900 overflow-hidden font-mono text-xs">
      {path && (
        <div className="bg-gray-800 px-4 py-2 text-gray-300 font-semibold border-b border-gray-700 flex items-center justify-between">
          <span>{path}</span>
          <span className="text-[10px] text-gray-400 font-normal">
            {lines.length} lines {isCapped && !isExpanded && `(showing first ${LINE_LIMIT})`}
          </span>
        </div>
      )}

      <div className="overflow-x-auto p-2">
        <table className="w-full border-collapse">
          <tbody>
            {displayedLines.map((line, idx) => {
              let rowBg = "text-gray-300";
              let linePrefix = " ";

              if (line.startsWith("+") && !line.startsWith("+++")) {
                rowBg = "bg-emerald-950/60 text-emerald-300";
                linePrefix = "+";
              } else if (line.startsWith("-") && !line.startsWith("---")) {
                rowBg = "bg-rose-950/60 text-rose-300";
                linePrefix = "-";
              } else if (line.startsWith("@@")) {
                rowBg = "bg-blue-950/50 text-blue-300 font-semibold";
                linePrefix = "@";
              }

              return (
                <tr key={idx} className={`leading-5 hover:bg-white/5 ${rowBg}`}>
                  <td className="w-12 select-none text-right pr-3 text-gray-500 font-mono text-[10px]">
                    {idx + 1}
                  </td>
                  <td className="w-4 select-none text-center font-bold text-[11px] opacity-75">
                    {linePrefix !== " " && linePrefix}
                  </td>
                  <td className="whitespace-pre font-mono pr-4 pl-1">
                    {/* Inert string rendering guarantees XSS safety */}
                    {line}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {isCapped && (
        <div className="bg-gray-800 px-4 py-2 border-t border-gray-700 flex items-center justify-between">
          <span className="text-gray-400 text-[11px]">
            {isExpanded
              ? `Showing all ${lines.length} lines.`
              : `Diff truncated at ${LINE_LIMIT} lines. (${lines.length - LINE_LIMIT} remaining)`}
          </span>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-blue-400 hover:text-blue-300 text-xs font-semibold cursor-pointer underline"
          >
            {isExpanded ? "Collapse diff" : "Expand full diff"}
          </button>
        </div>
      )}
    </div>
  );
}
