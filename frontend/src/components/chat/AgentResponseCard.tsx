"use client";

import React, { useState } from "react";
import { DeveloperResponse, ProposedPatch } from "@/types/developer";
import { ResearchResponse } from "@/types/chat";
import { UnifiedDiffViewer } from "@/components/developer/UnifiedDiffViewer";
import { SafeMarkdown } from "./SafeMarkdown";
import { CitationViewer } from "./CitationViewer";
import { api } from "@/services/apiClient";

interface AgentResponseCardProps {
  developerResult?: unknown;
  researchResult?: ResearchResponse | null;
  projectId?: number;
  onApplySuccess?: (res: DeveloperResponse) => void;
}

export function AgentResponseCard({
  developerResult,
  researchResult,
  projectId,
  onApplySuccess,
}: AgentResponseCardProps) {
  const [confirmApply, setConfirmApply] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [applySuccess, setApplySuccess] = useState<string | null>(null);
  const [copiedDoc, setCopiedDoc] = useState(false);

  // Cast developerResult safely
  const devRes = developerResult ? (developerResult as DeveloperResponse) : undefined;
  const hasDevContent = Boolean(
    devRes && (devRes.summary || (devRes.proposed_patches && devRes.proposed_patches.length > 0) || devRes.documentation)
  );

  const handleApply = async () => {
    if (!devRes || !projectId || isApplying) return;

    setIsApplying(true);
    setApplyError(null);
    setApplySuccess(null);

    try {
      const expected_file_hashes: Record<string, string> = {};
      if (devRes.proposed_patches) {
        for (const patch of devRes.proposed_patches) {
          if (patch.original_hash) {
            expected_file_hashes[patch.path] = patch.original_hash;
          }
        }
      }

      const payload = {
        task_type: devRes.task_type || "code_gen",
        prompt: devRes.summary || "Apply approved code changes",
        mode: "apply",
        expected_file_hashes:
          Object.keys(expected_file_hashes).length > 0 ? expected_file_hashes : undefined,
      };

      const res = await api.post<DeveloperResponse>(
        `/projects/${projectId}/developer`,
        payload
      );

      if (
        res.summary.toLowerCase().includes("aborted") ||
        res.summary.toLowerCase().includes("concurrent")
      ) {
        setApplyError("Conflict: Workspace files were modified concurrently. Apply aborted.");
      } else {
        setApplySuccess("Changes successfully applied to workspace disk.");
        setConfirmApply(false);
        if (onApplySuccess) onApplySuccess(res);
      }
    } catch (err: unknown) {
      setApplyError(err instanceof Error ? err.message : "Failed to apply changes to disk.");
    } finally {
      setIsApplying(false);
    }
  };

  const handleCopyDoc = (docText: string) => {
    navigator.clipboard.writeText(docText);
    setCopiedDoc(true);
    setTimeout(() => setCopiedDoc(false), 2000);
  };

  const handleDownloadDoc = (docText: string) => {
    const blob = new Blob([docText], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "documentation.md";
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 my-2">
      {/* Research Result Citations */}
      {researchResult && <CitationViewer researchResult={researchResult} />}

      {/* Developer Intelligence Card */}
      {hasDevContent && devRes && (
        <div className="rounded-xl border border-white/[0.08] bg-[#15151B] p-4.5 space-y-4">
          {/* Header Badges */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] pb-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-[#5146FF]/15 text-[#8B7CFF] border border-[#5146FF]/30">
                <svg className="w-3.5 h-3.5 text-[#5146FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                </svg>
                {devRes.task_type === "code_gen"
                  ? "Code Generation"
                  : devRes.task_type === "repo_analysis"
                  ? "Repository Intelligence"
                  : devRes.task_type === "doc_gen"
                  ? "Documentation Generator"
                  : "Developer Task"}
              </span>

              <span
                className={`text-[11px] font-medium px-2 py-0.5 rounded border ${
                  devRes.mode === "apply"
                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                    : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                }`}
              >
                {devRes.mode === "apply" ? "Applied to Disk" : "Dry-run Preview"}
              </span>

              {devRes.status && (
                <span
                  className={`text-[11px] font-medium px-2 py-0.5 rounded border ${
                    devRes.status === "success"
                      ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                      : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                  }`}
                >
                  {devRes.status.toUpperCase()}
                </span>
              )}
            </div>
          </div>

          {/* Narrative Summary */}
          {devRes.summary && (
            <div className="text-xs text-[#F5F5F5] leading-relaxed">
              <SafeMarkdown content={devRes.summary} />
            </div>
          )}

          {/* Files Analyzed */}
          {devRes.files_analyzed && devRes.files_analyzed.length > 0 && (
            <div className="space-y-1.5">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-[#929292]">
                Files Analyzed ({devRes.files_analyzed.length})
              </span>
              <div className="flex flex-wrap gap-1.5">
                {devRes.files_analyzed.map((f, i) => (
                  <span
                    key={i}
                    className="px-2 py-0.5 rounded bg-[#20212B] text-[11px] font-mono text-[#A4A6B8] border border-white/[0.06]"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Warnings */}
          {devRes.warnings && devRes.warnings.length > 0 && (
            <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 text-xs text-amber-300 space-y-1">
              <p className="font-semibold flex items-center gap-1.5">
                <span>⚠️</span> Diagnostic Warnings ({devRes.warnings.length})
              </p>
              <ul className="list-disc list-inside space-y-0.5 text-[11px] text-amber-200/80">
                {devRes.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Proposed Patches */}
          {devRes.proposed_patches && devRes.proposed_patches.length > 0 && (
            <div className="space-y-4 pt-2">
              <span className="text-[11px] uppercase tracking-wider font-semibold text-[#929292]">
                Proposed Patches ({devRes.proposed_patches.length})
              </span>

              {devRes.proposed_patches.map((patch: ProposedPatch, idx: number) => {
                const isValidAST = patch.validation_status?.toLowerCase() === "valid";
                return (
                  <div
                    key={idx}
                    className="rounded-xl border border-white/[0.08] bg-[#20212B] overflow-hidden space-y-3 p-3.5"
                  >
                    {/* Patch Header */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] pb-2.5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-medium text-[#F8F8FC]">
                          {patch.path}
                        </span>
                        {patch.applied && (
                          <span className="text-[10px] bg-emerald-500/15 text-emerald-400 px-1.5 py-0.5 rounded font-mono">
                            Applied
                          </span>
                        )}
                      </div>

                      {/* AST Validation Badge */}
                      <div>
                        {isValidAST ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                            ✓ AST Syntax Valid
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-500/15 text-rose-400 border border-rose-500/30">
                            ✕ AST Syntax Invalid (Apply Blocked)
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Hashes */}
                    <div className="flex flex-wrap items-center gap-4 text-[10px] font-mono text-[#929292]">
                      <span>
                        Original:{" "}
                        <span className="text-[#A4A6B8]">
                          {patch.original_hash ? patch.original_hash.slice(0, 16) + "..." : "None"}
                        </span>
                      </span>
                      <span>
                        New:{" "}
                        <span className="text-[#A4A6B8]">
                          {patch.new_hash ? patch.new_hash.slice(0, 16) + "..." : "None"}
                        </span>
                      </span>
                    </div>

                    {/* Unified Diff */}
                    <UnifiedDiffViewer diff={patch.diff} path={patch.path} />
                  </div>
                );
              })}

              {/* Guarded Apply Changes Button */}
              {devRes.mode === "preview" && (
                <div className="pt-2">
                  {applyError && (
                    <div className="mb-3 rounded-lg bg-rose-500/10 border border-rose-500/20 p-2.5 text-xs text-rose-300">
                      {applyError}
                    </div>
                  )}
                  {applySuccess && (
                    <div className="mb-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-2.5 text-xs text-emerald-300">
                      {applySuccess}
                    </div>
                  )}

                  {!confirmApply ? (
                    <button
                      type="button"
                      onClick={() => setConfirmApply(true)}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#5146FF] hover:bg-[#4338e8] text-white text-xs font-semibold shadow-sm transition active:scale-95 cursor-pointer"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <span>Apply Changes to Workspace</span>
                    </button>
                  ) : (
                    <div className="p-3.5 rounded-xl border border-amber-500/30 bg-[#20212B] flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold text-[#F8F8FC]">
                          Confirm Modification of Workspace Files?
                        </p>
                        <p className="text-[11px] text-[#A4A6B8]">
                          Optimistic concurrency verifies base SHA-256 hashes before modifying disk.
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setConfirmApply(false)}
                          disabled={isApplying}
                          className="px-3 py-1.5 rounded-lg border border-white/[0.1] text-xs font-medium text-[#A4A6B8] hover:bg-white/[0.04]"
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={handleApply}
                          disabled={isApplying}
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition"
                        >
                          {isApplying ? "Applying..." : "Confirm & Apply"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Generated Documentation */}
          {devRes.documentation && (
            <div className="rounded-xl border border-white/[0.08] bg-[#20212B] p-4 space-y-3">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2.5">
                <span className="text-xs font-semibold text-[#F8F8FC]">Generated Documentation</span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleCopyDoc(devRes.documentation || "")}
                    className="px-2.5 py-1 rounded bg-[#15151B] border border-white/[0.08] text-[11px] font-medium text-[#A4A6B8] hover:text-white transition"
                  >
                    {copiedDoc ? "Copied!" : "Copy"}
                  </button>
                  <button
                    onClick={() => handleDownloadDoc(devRes.documentation || "")}
                    className="px-2.5 py-1 rounded bg-[#15151B] border border-white/[0.08] text-[11px] font-medium text-[#8B7CFF] hover:text-white transition"
                  >
                    Download .md
                  </button>
                </div>
              </div>
              <div className="text-xs text-[#F5F5F5] max-h-96 overflow-y-auto pr-1">
                <SafeMarkdown content={devRes.documentation} />
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fallback for Unknown Structured Object */}
      {Boolean(developerResult && !hasDevContent) && (
        <details className="rounded-xl border border-white/[0.08] bg-[#15151B] p-3 text-xs text-[#A4A6B8]">
          <summary className="font-mono text-[11px] cursor-pointer text-[#8B7CFF] hover:underline">
            View Structured Developer Payload
          </summary>
          <pre className="mt-2 p-2.5 rounded bg-[#20212B] overflow-x-auto text-[11px] font-mono text-[#F5F5F5]">
            {JSON.stringify(developerResult, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}
