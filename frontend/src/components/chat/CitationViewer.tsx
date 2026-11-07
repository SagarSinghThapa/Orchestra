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
    <div className="mt-4 pt-3 border-t border-white/[0.06]">
      {status === "insufficient_evidence" && (
        <div className="mb-3 rounded-lg bg-amber-500/10 p-3 border border-amber-500/20 text-xs text-amber-300">
          <div className="flex items-center gap-1.5 font-semibold">
            <svg
              className="h-4 w-4 text-amber-400 flex-shrink-0"
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
          <p className="mt-1 text-amber-200/80">
            Available indexed documents lacked sufficient verified evidence to fully substantiate
            all aspects of this inquiry.
          </p>
        </div>
      )}

      {citations && citations.length > 0 && (
        <div>
          <div className="text-[11px] font-semibold text-[#929292] uppercase tracking-wider mb-2">
            Verified Citations ({citations.length})
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            {citations.map((c, idx) => {
              const isSelected = activeCitation?.citation_id === c.citation_id;
              return (
                <button
                  key={c.citation_id || idx}
                  onClick={() => setActiveCitation(isSelected ? null : c)}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
                    isSelected
                      ? "bg-[#5146FF] text-white border-[#5146FF] shadow-sm"
                      : "bg-[#20212B] text-[#A4A6B8] border-white/[0.08] hover:bg-[#262836] hover:text-[#F8F8FC]"
                  }`}
                  title={`${c.document_filename} (Page ${c.page_number})`}
                >
                  <span className="font-bold text-[#8B7CFF]">[{idx + 1}]</span>
                  <span className="truncate max-w-[120px]">{c.document_filename}</span>
                  <span className="text-[10px] opacity-75">p.{c.page_number}</span>
                </button>
              );
            })}
          </div>

          {/* Active Citation Card Popover */}
          {activeCitation && (
            <div className="mt-3 p-3.5 bg-[#20212B] rounded-xl border border-[#5146FF]/30 shadow-2xl animate-in fade-in duration-150">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2 mb-2">
                <div className="flex items-center gap-2">
                  <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-[#5146FF]/20 text-[#8B7CFF] border border-[#5146FF]/30">
                    Doc #{activeCitation.document_id}
                  </span>
                  <span className="text-xs font-semibold text-[#F8F8FC] truncate max-w-[200px]">
                    {activeCitation.document_filename}
                  </span>
                  <span className="text-xs text-[#929292]">Page {activeCitation.page_number}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                    Score: {typeof activeCitation.score === "number" ? activeCitation.score.toFixed(3) : activeCitation.score}
                  </span>
                  <button
                    onClick={() => setActiveCitation(null)}
                    className="text-[#929292] hover:text-[#F8F8FC] text-xs font-bold p-0.5 cursor-pointer"
                    aria-label="Close citation details"
                  >
                    ✕
                  </button>
                </div>
              </div>

              <div className="text-xs text-[#F5F5F5] font-serif leading-relaxed bg-[#15151B] p-2.5 rounded-lg border border-white/[0.04] italic max-h-48 overflow-y-auto">
                &ldquo;{activeCitation.text}&rdquo;
              </div>

              <div className="mt-2 text-[10px] text-[#929292] font-mono">
                Chunk: {activeCitation.chunk_id || "N/A"} | Char Range: {activeCitation.start_char} - {activeCitation.end_char}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
