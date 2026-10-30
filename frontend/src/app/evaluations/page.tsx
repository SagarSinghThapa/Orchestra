"use client";

import React, { useState, useEffect, useMemo, useRef } from "react";
import { useAuth } from "@/features/auth/useAuth";
import { useProject } from "@/features/projects/ProjectContext";
import { api, ApiError } from "@/services/apiClient";
import {
  BenchmarkSuiteInfo,
  EvaluationRun,
  EvaluationRunCreate,
  ExecutionMode,
} from "@/types/evaluations";
import { MetricCard } from "@/components/evaluations/MetricCard";
import { RunsTable } from "@/components/evaluations/RunsTable";
import { RunEvaluationModal } from "@/components/evaluations/RunEvaluationModal";
import { RunInspectorModal } from "@/components/evaluations/RunInspectorModal";

export default function EvaluationsPage() {
  const { user } = useAuth();
  const { selectedProject } = useProject();

  const isViewer = user?.role === "viewer";

  const [suites, setSuites] = useState<BenchmarkSuiteInfo[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [executionLoading, setExecutionLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const [isRunModalOpen, setIsRunModalOpen] = useState<boolean>(false);
  const [isInspectorModalOpen, setIsInspectorModalOpen] = useState<boolean>(false);
  const [inspectedRun, setInspectedRun] = useState<EvaluationRun | null>(null);

  const activeAbortController = useRef<AbortController | null>(null);

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    activeAbortController.current = controller;

    const loadData = async () => {
      try {
        const [suitesResp, runsResp] = await Promise.all([
          api.get<BenchmarkSuiteInfo[]>("/evaluations/benchmarks", {
            signal: controller.signal,
          }),
          api.get<EvaluationRun[]>(
            `/evaluations/runs${selectedProject ? `?project_id=${selectedProject.id}` : ""}`,
            { signal: controller.signal }
          ),
        ]);

        if (active) {
          setSuites(suitesResp);
          setRuns(runsResp);
          setError(null);
        }
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          return;
        }
        if (active) {
          const msg = err instanceof ApiError ? err.message : "Failed to load evaluation data";
          setError(msg);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    loadData();

    return () => {
      active = false;
      controller.abort();
    };
  }, [selectedProject]);

  // Derived metrics from latest run and active baseline
  const activeBaseline = useMemo(() => {
    return runs.find((r) => r.is_baseline && r.status === "completed") || null;
  }, [runs]);

  const latestCompletedRun = useMemo(() => {
    return runs.find((r) => r.status === "completed") || null;
  }, [runs]);

  const getMetricValue = (run: EvaluationRun | null, ...keys: string[]): number | null => {
    if (!run || !run.summary_metrics) return null;
    for (const k of keys) {
      if (k in run.summary_metrics) {
        return run.summary_metrics[k];
      }
    }
    return null;
  };

  const handleLaunchRun = async (params: {
    suite_id: string;
    project_id?: number | null;
    execution_mode: ExecutionMode;
    max_cases: number;
  }) => {
    try {
      setExecutionLoading(true);
      setError(null);

      const payload: EvaluationRunCreate = {
        suite_id: params.suite_id,
        project_id: params.project_id,
        execution_mode: params.execution_mode,
        max_cases: params.max_cases,
      };

      const newRun = await api.post<EvaluationRun>("/evaluations/runs", payload);

      // Prepend to runs list
      setRuns((prev) => [newRun, ...prev]);

      // Automatically open inspector for immediate feedback
      setInspectedRun(newRun);
      setIsInspectorModalOpen(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to execute benchmark run";
      setError(msg);
    } finally {
      setExecutionLoading(false);
    }
  };

  const handleInspect = async (run: EvaluationRun) => {
    try {
      // If granular results not yet loaded, fetch full run detail
      if (!run.case_results || run.case_results.length === 0) {
        const fullRun = await api.get<EvaluationRun>(`/evaluations/runs/${run.id}`);
        setInspectedRun(fullRun);
      } else {
        setInspectedRun(run);
      }
      setIsInspectorModalOpen(true);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to load run details";
      setError(msg);
    }
  };

  const handleSetBaseline = async (runId: string) => {
    try {
      const updatedRun = await api.post<EvaluationRun>(`/evaluations/runs/${runId}/baseline`);
      setRuns((prev) =>
        prev.map((r) => {
          if (r.id === runId) return updatedRun;
          if (r.suite_id === updatedRun.suite_id && r.project_id === updatedRun.project_id) {
            return { ...r, is_baseline: false };
          }
          return r;
        })
      );
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to promote run to baseline";
      setError(msg);
    }
  };

  const handleDeleteRun = async (runId: string) => {
    try {
      await api.delete(`/evaluations/runs/${runId}`);
      setRuns((prev) => prev.filter((r) => r.id !== runId));
      if (inspectedRun?.id === runId) {
        setIsInspectorModalOpen(false);
        setInspectedRun(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to delete evaluation run";
      setError(msg);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6 pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
              Model &amp; Agent Evaluations
            </h1>
            {isViewer && (
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200">
                Viewer Role (Read Only)
              </span>
            )}
          </div>
          <p className="text-xs sm:text-sm text-gray-500 mt-1">
            Automated deterministic benchmarking suite for multi-agent intelligence, citation grounding, and safety telemetry.
          </p>
        </div>

        <div>
          <button
            type="button"
            disabled={isViewer || executionLoading}
            onClick={() => setIsRunModalOpen(true)}
            title={isViewer ? "Viewers cannot launch benchmark runs" : undefined}
            className="px-4 py-2.5 text-xs sm:text-sm font-bold rounded-xl bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-xs transition-colors flex items-center space-x-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>Run Benchmark</span>
          </button>
        </div>
      </div>

      {/* Global Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-rose-500 hover:text-rose-700 font-bold ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Synchronous Execution Loading Banner */}
      {executionLoading && (
        <div className="rounded-xl border border-blue-200 bg-blue-50/70 p-4 shadow-xs animate-pulse">
          <div className="flex items-center space-x-3">
            <svg className="animate-spin h-5 w-5 text-blue-600" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v8H4z"
              />
            </svg>
            <div>
              <span className="font-bold text-sm text-blue-900 block">
                Executing benchmark suite...
              </span>
              <span className="text-xs text-blue-700">
                Evaluating test cases sequentially to preserve latency accuracy. Zero fabricated progress.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Primary Metric Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="RAG Faithfulness"
          value={getMetricValue(latestCompletedRun, "rag_faithfulness", "faithfulness_rate")}
          baselineValue={getMetricValue(activeBaseline, "rag_faithfulness", "faithfulness_rate")}
          unit="%"
          direction="higher_is_better"
          description="Citation precision and claim grounding"
        />

        <MetricCard
          label="Citation Precision"
          value={getMetricValue(latestCompletedRun, "citation_precision")}
          baselineValue={getMetricValue(activeBaseline, "citation_precision")}
          unit="%"
          direction="higher_is_better"
          description="Ratio of relevant citations over total citations"
        />

        <MetricCard
          label="Coding AST Validity"
          value={getMetricValue(latestCompletedRun, "ast_syntax_validity", "syntax_validity")}
          baselineValue={getMetricValue(activeBaseline, "ast_syntax_validity", "syntax_validity")}
          unit="%"
          direction="higher_is_better"
          description="Tree-sitter parser validation score"
        />

        <MetricCard
          label="P95 Latency"
          value={getMetricValue(latestCompletedRun, "p95_latency_ms")}
          baselineValue={getMetricValue(activeBaseline, "p95_latency_ms")}
          unit="ms"
          direction="lower_is_better"
          description="Nearest-rank 95th percentile turn time"
        />
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="p-12 text-center bg-white rounded-xl border border-gray-200">
          <svg className="animate-spin h-6 w-6 text-blue-600 mx-auto mb-3" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <p className="text-xs text-gray-500 font-medium">Loading evaluation runs and benchmarks...</p>
        </div>
      ) : runs.length === 0 ? (
        /* Honest Empty State — Zero Mock Metrics */
        <div className="text-center py-16 px-4 bg-white rounded-2xl border-2 border-dashed border-gray-200 shadow-2xs">
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <h3 className="text-base font-bold text-gray-900 mb-1">
            No evaluation runs recorded
          </h3>
          <p className="text-xs text-gray-500 max-w-md mx-auto mb-6">
            Run your first benchmark suite to evaluate system intelligence and track regression metrics.
          </p>
          <button
            type="button"
            disabled={isViewer || executionLoading}
            onClick={() => setIsRunModalOpen(true)}
            title={isViewer ? "Viewers cannot launch benchmark runs" : undefined}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-xs transition-colors"
          >
            Run Benchmark
          </button>
        </div>
      ) : (
        /* Historical Runs Table */
        <RunsTable
          runs={runs}
          isViewer={isViewer}
          onInspect={handleInspect}
          onSetBaseline={handleSetBaseline}
          onDelete={handleDeleteRun}
        />
      )}

      {/* Modals */}
      <RunEvaluationModal
        isOpen={isRunModalOpen}
        onClose={() => setIsRunModalOpen(false)}
        suites={suites}
        currentProjectId={selectedProject?.id || null}
        onSubmit={handleLaunchRun}
        isLoading={executionLoading}
        isViewer={isViewer}
      />

      <RunInspectorModal
        isOpen={isInspectorModalOpen}
        onClose={() => {
          setIsInspectorModalOpen(false);
          setInspectedRun(null);
        }}
        run={inspectedRun}
      />
    </div>
  );
}
