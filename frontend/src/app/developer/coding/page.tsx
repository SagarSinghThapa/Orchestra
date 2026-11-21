"use client";

import React, { useState } from "react";
import { useProject } from "@/features/projects/ProjectContext";
import { useAuth } from "@/features/auth/AuthContext";
import { api } from "@/services/apiClient";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/StateWrappers";
import { ClassificationBanner } from "@/components/developer/ClassificationBanner";
import { UnifiedDiffViewer } from "@/components/developer/UnifiedDiffViewer";
import { DeveloperRequest, DeveloperResponse } from "@/types/developer";

export default function CodingAssistantPage() {
  const { selectedProject } = useProject();
  const { user } = useAuth();

  const [prompt, setPrompt] = useState("");
  const [targetFilesInput, setTargetFilesInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<DeveloperResponse | null>(null);
  const [appliedResponse, setAppliedResponse] = useState<DeveloperResponse | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  const isViewer = user?.role === "viewer";

  const parseTargetFiles = (): string[] | undefined => {
    const list = targetFilesInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    return list.length > 0 ? list : undefined;
  };

  const handleGenerateProposal = async () => {
    if (!prompt.trim() || !selectedProject) return;

    setLoading(true);
    setError(null);
    setAppliedResponse(null);

    try {
      const payload: DeveloperRequest = {
        task_type: "code_gen",
        prompt: prompt.trim(),
        mode: "preview",
        target_files: parseTargetFiles(),
      };

      const res = await api.post<DeveloperResponse>(
        `/projects/${selectedProject.id}/developer`,
        payload
      );
      setProposal(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate code proposal");
    } finally {
      setLoading(false);
    }
  };

  const handleApplyChanges = async () => {
    if (!proposal || !selectedProject || isViewer) return;

    setApplying(true);
    setError(null);
    setShowConfirmModal(false);

    try {
      // Gather original file hashes for optimistic concurrency guard
      const expected_file_hashes: Record<string, string> = {};
      for (const patch of proposal.proposed_patches) {
        if (patch.original_hash) {
          expected_file_hashes[patch.path] = patch.original_hash;
        }
      }

      const payload: DeveloperRequest = {
        task_type: "code_gen",
        prompt: prompt.trim(),
        mode: "apply",
        target_files: parseTargetFiles(),
        expected_file_hashes:
          Object.keys(expected_file_hashes).length > 0 ? expected_file_hashes : undefined,
      };

      const res = await api.post<DeveloperResponse>(
        `/projects/${selectedProject.id}/developer`,
        payload
      );
      if (
        res.summary.toLowerCase().includes("aborted") ||
        res.summary.toLowerCase().includes("concurrent")
      ) {
        setError(
          "Workspace files were modified concurrently. Base hashes no longer match. Apply aborted."
        );
      } else {
        setAppliedResponse(res);
      }
      setProposal(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to apply code modifications";
      if (
        msg.toLowerCase().includes("base hash mismatch") ||
        msg.toLowerCase().includes("modified concurrently")
      ) {
        setError(
          "Workspace files were modified concurrently. Base hashes no longer match. Please regenerate the proposal."
        );
      } else {
        setError(msg);
      }
    } finally {
      setApplying(false);
    }
  };

  if (!selectedProject) {
    return (
      <div className="p-8 workspace-gradient-bg min-h-[calc(100vh-3.5rem)]">
        <div className="max-w-4xl mx-auto py-12 px-4">
          <EmptyState
            title="No Project Selected"
            description="Please select or create an active project workspace to use the Coding Assistant."
          />
        </div>
      </div>
    );
  }

  const hasInvalidAst = proposal?.proposed_patches.some(
    (p) =>
      p.validation_status.toLowerCase() !== "valid" &&
      !p.validation_status.toLowerCase().startsWith("skipped")
  );

  return (
    <div className="p-6 sm:p-8 space-y-6 max-w-5xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#F8F8FC] tracking-tight">
            Autonomous Coding Assistant
          </h1>
          <p className="text-xs sm:text-sm text-[#A4A6B8] mt-1 max-w-2xl">
            Two-stage verified code synthesis: generate and review diffs before applying to host disk.
          </p>
        </div>
        <span className="text-xs font-medium px-3 py-1 bg-[#20212B] text-[#8B7CFF] rounded-lg border border-white/[0.08]">
          Workspace: {selectedProject.name}
        </span>
      </div>

      <ClassificationBanner />

      {error && (
        <div className="rounded-xl bg-rose-500/10 p-4 border border-rose-500/20 text-xs text-rose-300 flex items-start justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-rose-400 hover:text-rose-200 font-bold ml-4 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* Applied Confirmation Banner */}
      {appliedResponse && (
        <div className="rounded-xl bg-emerald-500/15 p-5 border border-emerald-500/30">
          <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm mb-1">
            <svg className="h-5 w-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span>Changes Applied Successfully to Disk</span>
          </div>
          <p className="text-xs text-emerald-300/90">{appliedResponse.summary}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {appliedResponse.proposed_patches.map((p, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-[#20212B] border border-emerald-500/30 text-emerald-300 font-mono"
              >
                ✓ {p.path}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Stage 1: Proposal Input */}
      <Card>
        <div className="space-y-4">
          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#929292] mb-1.5">
              Task Prompt (1 - 4,000 characters)
            </label>
            <textarea
              placeholder="Describe the feature, bugfix, or refactor to implement across the workspace..."
              rows={4}
              maxLength={4000}
              className="w-full bg-[#15151B] border border-white/[0.08] rounded-xl p-3.5 text-xs text-[#F5F5F5] placeholder-[#929292] focus:outline-none focus:border-[#5146FF] transition resize-none"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={loading || applying}
            />
            <div className="text-right text-[11px] font-mono text-[#929292] mt-1">
              {prompt.length} / 4000 characters
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#929292] mb-1.5">
              Target Files (Optional, comma-separated relative paths)
            </label>
            <input
              type="text"
              placeholder="e.g. app/main.py, tests/test_main.py"
              className="w-full bg-[#15151B] border border-white/[0.08] rounded-xl px-3.5 py-2.5 text-xs text-[#F5F5F5] placeholder-[#929292] focus:outline-none focus:border-[#5146FF] transition"
              value={targetFilesInput}
              onChange={(e) => setTargetFilesInput(e.target.value)}
              disabled={loading || applying}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-white/[0.06]">
            <span className="text-xs text-[#929292] italic">
              Stage 1 executes dry-run preview with AST syntax validation.
            </span>
            <button
              onClick={handleGenerateProposal}
              disabled={loading || applying || !prompt.trim()}
              className="px-5 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#5146FF] hover:bg-[#4338e8] disabled:opacity-50 disabled:cursor-not-allowed transition-all active:scale-95 shadow-sm cursor-pointer"
            >
              {loading ? "Synthesizing Proposal..." : "Generate Proposal (Preview)"}
            </button>
          </div>
        </div>
      </Card>

      {/* Stage 2: Proposal Review & Diff Inspection */}
      {proposal && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <Card>
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] pb-3">
                <div>
                  <h2 className="text-base font-semibold text-[#F8F8FC]">Synthesized Proposal Review</h2>
                  <p className="text-xs text-[#929292] mt-0.5">
                    Carefully review the proposed patch diffs and syntax validation before applying.
                  </p>
                </div>
                <span className="text-xs font-medium px-2.5 py-1 bg-[#5146FF]/15 text-[#8B7CFF] rounded-lg border border-[#5146FF]/30">
                  {proposal.proposed_patches.length} files modified
                </span>
              </div>

              {/* Narrative Summary */}
              <div className="bg-[#15151B] p-4 rounded-xl border border-white/[0.06] text-xs text-[#F5F5F5] leading-relaxed">
                {proposal.summary}
              </div>

              {/* Warnings if any */}
              {proposal.warnings && proposal.warnings.length > 0 && (
                <div className="rounded-xl bg-amber-500/10 p-3.5 border border-amber-500/20 text-xs text-amber-300 space-y-1">
                  <div className="font-semibold">Compiler / Linter Warnings:</div>
                  <ul className="list-disc pl-5 space-y-0.5 text-amber-200/80">
                    {proposal.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Proposed Patches */}
              <div className="space-y-4 pt-2">
                {proposal.proposed_patches.map((patch, idx) => {
                  const isValid =
                    patch.validation_status.toLowerCase() === "valid" ||
                    patch.validation_status.toLowerCase().startsWith("skipped");
                  return (
                    <div key={idx} className="space-y-2 rounded-xl bg-[#15151B] p-3 border border-white/[0.06]">
                      <div className="flex items-center justify-between text-xs font-mono">
                        <span className="font-medium text-[#F8F8FC]">{patch.path}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                            isValid
                              ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                              : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                          }`}
                        >
                          AST: {patch.validation_status}
                        </span>
                      </div>
                      <UnifiedDiffViewer diff={patch.diff} path={patch.path} />
                    </div>
                  );
                })}
              </div>

              {/* Stage 3: Explicit Apply Action */}
              <div className="pt-4 border-t border-white/[0.06] flex flex-wrap items-center justify-between gap-3">
                <div>
                  {isViewer && (
                    <p className="text-xs text-amber-400 font-medium">
                      Viewer role is not authorized to apply code modifications.
                    </p>
                  )}
                  {hasInvalidAst && (
                    <p className="text-xs text-rose-400 font-medium">
                      Cannot apply changes: one or more files failed AST validation.
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setProposal(null)}
                    disabled={applying}
                    className="px-4 py-2 text-xs font-semibold text-[#A4A6B8] hover:text-[#F8F8FC] transition cursor-pointer"
                  >
                    Discard Proposal
                  </button>

                  <button
                    onClick={() => setShowConfirmModal(true)}
                    disabled={applying || isViewer || hasInvalidAst}
                    className="px-6 py-2.5 rounded-xl text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-all active:scale-95 shadow-sm cursor-pointer"
                  >
                    {applying ? "Applying Modifications..." : "Apply to Workspace"}
                  </button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-[#20212B] border border-white/[0.12] rounded-2xl shadow-2xl max-w-md w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <h3 className="text-base font-semibold text-[#F8F8FC] mb-2">Confirm Code Application</h3>
            <p className="text-xs text-[#A4A6B8] leading-relaxed mb-4">
              Apply changes to workspace? This will write verified patch modifications to the host filesystem.
              Optimistic concurrency guards will verify file hashes before writing.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowConfirmModal(false)}
                className="px-4 py-2 text-xs font-semibold text-[#A4A6B8] hover:text-[#F8F8FC] transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleApplyChanges}
                className="px-5 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl shadow-sm transition active:scale-95 cursor-pointer"
              >
                Yes, Write to Disk
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
