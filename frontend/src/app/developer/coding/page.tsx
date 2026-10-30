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
      setAppliedResponse(res);
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
      <div className="max-w-4xl mx-auto py-12 px-4">
        <EmptyState
          title="No Project Selected"
          description="Please select or create an active project workspace to use the Coding Assistant."
        />
      </div>
    );
  }

  const hasInvalidAst = proposal?.proposed_patches.some(
    (p) => p.validation_status.toLowerCase() !== "valid"
  );

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Autonomous Coding Assistant</h1>
          <p className="text-sm text-gray-500 mt-1">
            Two-stage verified code synthesis: generate and review diffs before applying to host disk.
          </p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 bg-gray-100 text-gray-700 rounded-full border">
          Workspace: {selectedProject.name}
        </span>
      </div>

      <ClassificationBanner />

      {error && (
        <div className="rounded-lg bg-red-50 p-4 border border-red-200 text-sm text-red-700 flex items-start justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-red-500 hover:text-red-700 font-bold ml-4 cursor-pointer"
          >
            ✕
          </button>
        </div>
      )}

      {/* Applied Confirmation Banner */}
      {appliedResponse && (
        <div className="rounded-lg bg-emerald-50 p-5 border border-emerald-200">
          <div className="flex items-center gap-2 text-emerald-800 font-bold text-base mb-1">
            <svg className="h-5 w-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span>Changes Applied Successfully to Disk</span>
          </div>
          <p className="text-xs text-emerald-700">{appliedResponse.summary}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {appliedResponse.proposed_patches.map((p, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded bg-white border border-emerald-300 text-emerald-800 font-mono"
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
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">
              Task Prompt (1 - 4,000 characters)
            </label>
            <textarea
              placeholder="Describe the feature, bugfix, or refactor to implement across the workspace..."
              rows={4}
              maxLength={4000}
              className="w-full border border-gray-300 rounded-lg p-3 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={loading || applying}
            />
            <div className="text-right text-[11px] text-gray-400 mt-1">
              {prompt.length} / 4000 characters
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">
              Target Files (Optional, comma-separated relative paths)
            </label>
            <input
              type="text"
              placeholder="e.g. app/main.py, tests/test_main.py"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={targetFilesInput}
              onChange={(e) => setTargetFilesInput(e.target.value)}
              disabled={loading || applying}
            />
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-gray-100">
            <span className="text-xs text-gray-500 italic">
              Stage 1 executes dry-run preview with AST syntax validation.
            </span>
            <button
              onClick={handleGenerateProposal}
              disabled={loading || applying || !prompt.trim()}
              className="px-5 py-2.5 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
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
              <div className="flex items-center justify-between border-b pb-3">
                <div>
                  <h2 className="text-lg font-bold text-gray-900">Synthesized Proposal Review</h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Carefully review the proposed patch diffs and syntax validation before applying.
                  </p>
                </div>
                <span className="text-xs font-semibold px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full border border-blue-200">
                  {proposal.proposed_patches.length} files modified
                </span>
              </div>

              {/* Narrative Summary */}
              <div className="bg-gray-50 p-4 rounded-lg border text-sm text-gray-800 leading-relaxed">
                {proposal.summary}
              </div>

              {/* Warnings if any */}
              {proposal.warnings && proposal.warnings.length > 0 && (
                <div className="rounded-lg bg-amber-50 p-3.5 border border-amber-200 text-xs text-amber-800 space-y-1">
                  <div className="font-semibold">Compiler / Linter Warnings:</div>
                  <ul className="list-disc pl-5 space-y-0.5">
                    {proposal.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Proposed Patches */}
              <div className="space-y-4 pt-2">
                {proposal.proposed_patches.map((patch, idx) => {
                  const isValid = patch.validation_status.toLowerCase() === "valid";
                  return (
                    <div key={idx} className="space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono">
                        <span className="font-semibold text-gray-800">{patch.path}</span>
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            isValid
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                              : "bg-rose-100 text-rose-800 border border-rose-300"
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
              <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
                <div>
                  {isViewer && (
                    <p className="text-xs text-amber-600 font-medium">
                      Viewer role is not authorized to apply code modifications.
                    </p>
                  )}
                  {hasInvalidAst && (
                    <p className="text-xs text-rose-600 font-medium">
                      Cannot apply changes: one or more files failed AST validation.
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setProposal(null)}
                    disabled={applying}
                    className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-900 cursor-pointer"
                  >
                    Discard Proposal
                  </button>

                  <button
                    onClick={() => setShowConfirmModal(true)}
                    disabled={applying || isViewer || hasInvalidAst}
                    className="px-6 py-2.5 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 animate-in fade-in zoom-in-95 duration-150">
            <h3 className="text-base font-bold text-gray-900 mb-2">Confirm Code Application</h3>
            <p className="text-xs text-gray-600 leading-relaxed mb-4">
              Apply changes to workspace? This will write verified patch modifications to the host filesystem.
              Optimistic concurrency guards will verify file hashes before writing.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowConfirmModal(false)}
                className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-800 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleApplyChanges}
                className="px-5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm cursor-pointer"
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
