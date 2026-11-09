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
      <div className="p-8 workspace-gradient-bg min-h-[calc(100vh-3.5rem)]">
        <div className="max-w-4xl mx-auto py-12 px-4">
          <EmptyState
            title="No Project Selected"
            description="Please select or create an active project workspace to run Repository Intelligence."
          />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 sm:p-8 space-y-6 max-w-5xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#F8F8FC] tracking-tight">
            Repository Intelligence
          </h1>
          <p className="text-xs sm:text-sm text-[#A4A6B8] mt-1 max-w-2xl">
            Deep structural analysis of workspace architecture, dependencies, frameworks, and security risks.
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

      {/* Analysis Control */}
      <Card>
        <div className="space-y-3">
          <label className="block text-[11px] font-semibold uppercase tracking-wider text-[#929292]">
            Analysis Focus / Query
          </label>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              placeholder="e.g. Focus on API architecture and dependencies..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={loading}
              className="flex-1 bg-[#15151B] border border-white/[0.08] rounded-xl px-4 py-2.5 text-xs text-[#F5F5F5] placeholder-[#929292] focus:outline-none focus:border-[#5146FF] transition"
            />
            <button
              onClick={handleAnalyze}
              disabled={loading}
              className="px-5 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#5146FF] hover:bg-[#4338e8] disabled:opacity-50 transition-all active:scale-95 shadow-sm cursor-pointer whitespace-nowrap"
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
            <h2 className="text-base font-semibold text-[#F8F8FC] mb-2.5">Executive Summary</h2>
            <div className="bg-[#15151B] p-4.5 rounded-xl border border-white/[0.06] text-xs text-[#F5F5F5] leading-relaxed whitespace-pre-wrap">
              {result.summary}
            </div>
          </Card>

          {/* Files Inspected */}
          {result.files_analyzed && result.files_analyzed.length > 0 && (
            <Card>
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[#929292] mb-3">
                Files Inspected ({result.files_analyzed.length})
              </h2>
              <div className="flex flex-wrap gap-2 max-h-48 overflow-y-auto">
                {result.files_analyzed.map((f, idx) => (
                  <span
                    key={idx}
                    className="px-2.5 py-1 rounded-lg bg-[#15151B] text-[#A4A6B8] text-xs font-mono border border-white/[0.06]"
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
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[#929292] mb-3">
                Tool Execution Audit ({result.tool_events.length} events)
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left border-collapse">
                  <thead>
                    <tr className="border-b border-white/[0.06] bg-[#15151B] text-[#929292] font-semibold">
                      <th className="py-2.5 px-3">Tool</th>
                      <th className="py-2.5 px-3">Target Path</th>
                      <th className="py-2.5 px-3">Duration</th>
                      <th className="py-2.5 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {result.tool_events.map((evt, idx) => (
                      <tr key={idx} className="hover:bg-white/[0.02] font-mono transition-colors">
                        <td className="py-2.5 px-3 font-semibold text-[#F8F8FC]">{evt.tool_name}</td>
                        <td className="py-2.5 px-3 text-[#A4A6B8]">{evt.target_path || "N/A"}</td>
                        <td className="py-2.5 px-3 text-[#929292]">{evt.duration_ms.toFixed(1)} ms</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              evt.status === "success"
                                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                                : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
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
            <div className="rounded-xl bg-amber-500/10 p-4 border border-amber-500/20 text-xs text-amber-300">
              <div className="font-semibold mb-1">Diagnostic Warnings:</div>
              <ul className="list-disc pl-5 space-y-0.5 text-amber-200/80">
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
