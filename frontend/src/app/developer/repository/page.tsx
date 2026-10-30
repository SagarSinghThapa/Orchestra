"use client";

import React, { useState } from "react";
import { useProject } from "@/features/projects/ProjectContext";
import { api } from "@/services/apiClient";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/StateWrappers";
import { ClassificationBanner } from "@/components/developer/ClassificationBanner";
import { DeveloperRequest, DeveloperResponse } from "@/types/developer";

export default function RepositoryIntelPage() {
  const { selectedProject } = useProject();

  const [prompt, setPrompt] = useState("Analyze repository structure, language distribution, and architectural risks");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DeveloperResponse | null>(null);

  const handleAnalyze = async () => {
    if (!selectedProject || loading) return;

    setLoading(true);
    setError(null);

    try {
      const payload: DeveloperRequest = {
        task_type: "repo_analysis",
        prompt: prompt.trim() || "Analyze repository structure and metadata",
        mode: "preview",
      };

      const res = await api.post<DeveloperResponse>(
        `/projects/${selectedProject.id}/developer`,
        payload
      );
      setResult(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to analyze repository");
    } finally {
      setLoading(false);
    }
  };

  if (!selectedProject) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4">
        <EmptyState
          title="No Project Selected"
          description="Please select or create an active project workspace to run Repository Intelligence."
        />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Repository Intelligence</h1>
          <p className="text-sm text-gray-500 mt-1">
            Deep structural analysis of workspace architecture, dependencies, frameworks, and security risks.
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

      {/* Analysis Control */}
      <Card>
        <div className="space-y-3">
          <label className="block text-xs font-semibold uppercase tracking-wider text-gray-500">
            Analysis Focus / Query
          </label>
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="e.g. Focus on API architecture and dependencies..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={loading}
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="px-5 py-2 rounded-lg text-xs font-bold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors shadow-sm cursor-pointer whitespace-nowrap"
            >
              {loading ? "Analyzing Workspace..." : "Run Analysis"}
            </button>
          </div>
        </div>
      </Card>

      {/* Results View */}
      {result && (
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Executive Summary */}
          <Card>
            <h2 className="text-lg font-bold text-gray-900 mb-2">Executive Summary</h2>
            <div className="bg-gray-50 p-4 rounded-lg border text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {result.summary}
            </div>
          </Card>

          {/* Files Inspected */}
          {result.files_analyzed && result.files_analyzed.length > 0 && (
            <Card>
              <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-3">
                Files Inspected ({result.files_analyzed.length})
              </h2>
              <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
                {result.files_analyzed.map((f, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded bg-gray-100 text-gray-700 text-xs font-mono border"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </Card>
          )}

          {/* Tool Audit Events */}
          {result.tool_events && result.tool_events.length > 0 && (
            <Card>
              <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-3">
                Tool Execution Audit ({result.tool_events.length} events)
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b bg-gray-50 text-gray-600 font-semibold">
                      <th className="py-2 px-3">Tool</th>
                      <th className="py-2 px-3">Target Path</th>
                      <th className="py-2 px-3">Duration</th>
                      <th className="py-2 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.tool_events.map((evt, idx) => (
                      <tr key={idx} className="border-b hover:bg-gray-50 font-mono">
                        <td className="py-2 px-3 font-semibold text-gray-800">{evt.tool_name}</td>
                        <td className="py-2 px-3 text-gray-600">{evt.target_path || "N/A"}</td>
                        <td className="py-2 px-3 text-gray-500">{evt.duration_ms.toFixed(1)} ms</td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              evt.status === "success"
                                ? "bg-emerald-100 text-emerald-800"
                                : "bg-red-100 text-red-800"
                            }`}
                          >
                            {evt.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* Warnings */}
          {result.warnings && result.warnings.length > 0 && (
            <div className="rounded-lg bg-amber-50 p-4 border border-amber-200 text-xs text-amber-800">
              <div className="font-semibold mb-1">Diagnostic Warnings:</div>
              <ul className="list-disc pl-5 space-y-0.5">
                {result.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
