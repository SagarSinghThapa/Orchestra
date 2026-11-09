"use client";

import React, { useState } from "react";
import { useProject } from "@/features/projects/ProjectContext";
import { useAuth } from "@/features/auth/AuthContext";
import { api } from "@/services/apiClient";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/StateWrappers";
import { ClassificationBanner } from "@/components/developer/ClassificationBanner";
import { SafeMarkdown } from "@/components/chat/SafeMarkdown";
import { UnifiedDiffViewer } from "@/components/developer/UnifiedDiffViewer";
import { DeveloperRequest, DeveloperResponse } from "@/types/developer";

export default function DocumentationGeneratorPage() {
  const { selectedProject } = useProject();
  const { user } = useAuth();

  const [docType, setDocType] = useState("README");
  const [prompt, setPrompt] = useState("Generate comprehensive technical documentation for this repository");
  const [loading, setLoading] = useState(false);
  const [writing, setWriting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<DeveloperResponse | null>(null);
  const [writeSuccess, setWriteSuccess] = useState<DeveloperResponse | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  const isViewer = user?.role === "viewer";

  const handlePreview = async () => {
    if (!selectedProject || loading) return;

    setLoading(true);
    setError(null);
    setWriteSuccess(null);

    try {
      const payload: DeveloperRequest = {
        task_type: "doc_gen",
        prompt: prompt.trim() || `Generate ${docType} documentation`,
        mode: "preview",
        context_hints: { doc_type: docType },
      };

      const res = await api.post<DeveloperResponse>(
        `/projects/${selectedProject.id}/developer`,
        payload
      );
      setPreview(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate documentation preview");
    } finally {
      setLoading(false);
    }
  };

  const handleWriteToDisk = async () => {
    if (!preview || !selectedProject || isViewer) return;

    setWriting(true);
    setError(null);
    setShowConfirmModal(false);

    try {
      const expected_file_hashes: Record<string, string> = {};
      for (const patch of preview.proposed_patches) {
        if (patch.original_hash) {
          expected_file_hashes[patch.path] = patch.original_hash;
        }
      }

      const payload: DeveloperRequest = {
        task_type: "doc_gen",
        prompt: prompt.trim() || `Generate and write ${docType} documentation`,
        mode: "apply",
        context_hints: { doc_type: docType },
        expected_file_hashes:
          Object.keys(expected_file_hashes).length > 0 ? expected_file_hashes : undefined,
      };

      const res = await api.post<DeveloperResponse>(
        `/projects/${selectedProject.id}/developer`,
        payload
      );
      setWriteSuccess(res);
      setPreview(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to write documentation to disk");
    } finally {
      setWriting(false);
    }
  };

  if (!selectedProject) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4">
        <EmptyState
          title="No Project Selected"
          description="Please select or create an active project workspace to use the Documentation Generator."
        />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Documentation Generator</h1>
          <p className="text-sm text-gray-500 mt-1">
            Automated repository documentation synthesis with preview-before-write safety.
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

      {/* Write Success Banner */}
      {writeSuccess && (
        <div className="rounded-lg bg-emerald-50 p-5 border border-emerald-200">
          <div className="flex items-center gap-2 text-emerald-800 font-bold text-base mb-1">
            <svg className="h-5 w-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span>Documentation Written to Disk</span>
          </div>
          <p className="text-xs text-emerald-700">{writeSuccess.summary}</p>
        </div>
      )}

      {/* Generator Form */}
      <Card>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">
                Document Target
              </label>
              <select
                value={docType}
                onChange={(e) => setDocType(e.target.value)}
                disabled={loading || writing}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="README">README.md</option>
                <option value="architecture">Architecture Guide</option>
                <option value="api_reference">API Documentation</option>
                <option value="repository_summary">Repository Overview</option>
              </select>
            </div>

            <div className="md:col-span-2">
              <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">
                Custom Focus / Instructions
              </label>
              <input
                type="text"
                placeholder="e.g. Focus on deployment steps and environment configuration..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                disabled={loading || writing}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-gray-100">
            <span className="text-xs text-gray-500 italic">
              Stage 1 produces markdown preview without modifying workspace files.
            </span>
            <button
              onClick={handlePreview}
              disabled={loading || writing || !prompt.trim()}
              className="px-5 py-2.5 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-sm cursor-pointer"
            >
              {loading ? "Generating Preview..." : "Generate Preview"}
            </button>
          </div>
        </div>
      </Card>

      {/* Documentation Preview */}
      {preview && (
        <div className="space-y-6 animate-in fade-in duration-200">
          <Card>
            <div className="space-y-4">
              <div className="flex items-center justify-between border-b pb-3">
                <div>
                  <h2 className="text-lg font-bold text-gray-900">Generated Preview</h2>
                  <p className="text-xs text-gray-500 mt-0.5">
                    Review generated markdown structure before writing to disk.
                  </p>
                </div>
                <span className="text-xs font-semibold px-2.5 py-1 bg-purple-50 text-purple-700 rounded-full border border-purple-200">
                  Target: {docType}
                </span>
              </div>

              {/* Rendered Markdown */}
              <div className="p-4 bg-gray-50 rounded-lg border">
                <SafeMarkdown
                  content={preview.documentation || preview.summary || "No documentation generated."}
                />
              </div>

              {/* Patches if generated */}
              {preview.proposed_patches && preview.proposed_patches.length > 0 && (
                <div className="space-y-3 pt-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
                    File Modifications ({preview.proposed_patches.length})
                  </h3>
                  {preview.proposed_patches.map((patch, idx) => (
                    <UnifiedDiffViewer key={idx} diff={patch.diff} path={patch.path} />
                  ))}
                </div>
              )}

              {/* Action Controls */}
              <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
                <div>
                  {isViewer && (
                    <p className="text-xs text-amber-600 font-medium">
                      Viewer role is not authorized to write files to disk.
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setPreview(null)}
                    disabled={writing}
                    className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-900 cursor-pointer"
                  >
                    Discard Preview
                  </button>

                  <button
                    onClick={() => setShowConfirmModal(true)}
                    disabled={writing || isViewer}
                    className="px-6 py-2.5 rounded-lg text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
                  >
                    {writing ? "Writing to Disk..." : "Write to Workspace"}
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
            <h3 className="text-base font-bold text-gray-900 mb-2">Confirm File Write</h3>
            <p className="text-xs text-gray-600 leading-relaxed mb-4">
              Write documentation to workspace disk? This will modify or create files in the active project directory.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowConfirmModal(false)}
                className="px-4 py-2 text-xs font-semibold text-gray-600 hover:text-gray-800 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleWriteToDisk}
                className="px-5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm cursor-pointer"
              >
                Yes, Write Documentation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
