"use client";

import React, { useState } from "react";
import { ResearchResponse, VerifiedCitation } from "@/types/chat";

interface CitationViewerProps {
  researchResult: ResearchResponse;
}

export function CitationViewer({ researchResult }: CitationViewerProps) {
  const [activeCitation, setActiveCitation] = useState<VerifiedCitation | null>(null);

  const { status, citations } = researchResult;

  return (
    <div className="mt-4 pt-3 border-t border-gray-100">
      {status === "insufficient_evidence" && (
        <div className="mb-3 rounded-md bg-amber-50 p-3 border border-amber-200 text-xs text-amber-800">
          <div className="flex items-center gap-1.5 font-semibold">
            <svg
              className="h-4 w-4 text-amber-600 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <span>Insufficient Verified Evidence</span>
          </div>
          <p className="mt-1 text-amber-700">
            Available indexed documents lacked sufficient verified evidence to fully substantiate
            all aspects of this inquiry.
          </p>
        </div>
      )}

      {citations && citations.length > 0 && (
        <div>
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            Verified Citations ({citations.length})
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            {citations.map((c, idx) => {
              const isSelected = activeCitation?.citation_id === c.citation_id;
              return (
                <button
                  key={c.citation_id || idx}
                  onClick={() => setActiveCitation(isSelected ? null : c)}
                  className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                    isSelected
                      ? "bg-blue-600 text-white border-blue-600 shadow-sm"
                      : "bg-gray-50 text-gray-700 border-gray-200 hover:bg-gray-100 hover:border-gray-300"
                  }`}
                  title={`${c.document_filename} (Page ${c.page_number})`}
                >
                  <span className="font-bold">[{idx + 1}]</span>
                  <span className="truncate max-w-[120px]">{c.document_filename}</span>
                  <span className="text-[10px] opacity-75">p.{c.page_number}</span>
                </button>
              );
            })}
          </div>

          {/* Active Citation Card Popover */}
          {activeCitation && (
            <div className="mt-3 p-3.5 bg-white rounded-lg border border-blue-200 shadow-md animate-in fade-in duration-150">
              <div className="flex items-center justify-between border-b border-gray-100 pb-2 mb-2">
                <div className="flex items-center gap-2">
                  <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800">
                    Doc #{activeCitation.document_id}
                  </span>
                  <span className="text-xs font-semibold text-gray-800 truncate max-w-[200px]">
                    {activeCitation.document_filename}
                  </span>
                  <span className="text-xs text-gray-500">Page {activeCitation.page_number}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-mono text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                    Score: {typeof activeCitation.score === "number" ? activeCitation.score.toFixed(3) : activeCitation.score}
                  </span>
                  <button
                    onClick={() => setActiveCitation(null)}
                    className="text-gray-400 hover:text-gray-600 text-xs font-bold p-0.5"
                    aria-label="Close citation details"
                  >
                    ✕
                  </button>
                </div>
              </div>

              <div className="text-xs text-gray-700 font-serif leading-relaxed bg-gray-50 p-2.5 rounded border border-gray-100 italic max-h-48 overflow-y-auto">
                &ldquo;{activeCitation.text}&rdquo;
              </div>

              <div className="mt-2 text-[10px] text-gray-400 font-mono">
                Chunk: {activeCitation.chunk_id || "N/A"} | Char Range: {activeCitation.start_char} - {activeCitation.end_char}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
