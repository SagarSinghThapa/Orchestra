import React, { useState } from "react";
import { BenchmarkSuiteInfo, ExecutionMode } from "@/types/evaluations";

interface RunEvaluationModalProps {
  isOpen: boolean;
  onClose: () => void;
  suites: BenchmarkSuiteInfo[];
  currentProjectId: number | null;
  onSubmit: (params: {
    suite_id: string;
    project_id?: number | null;
    execution_mode: ExecutionMode;
    max_cases: number;
  }) => Promise<void>;
  isLoading: boolean;
  isViewer: boolean;
}

export function RunEvaluationModal({
  isOpen,
  onClose,
  suites,
  currentProjectId,
  onSubmit,
  isLoading,
  isViewer,
}: RunEvaluationModalProps) {
  const [selectedSuiteId, setSelectedSuiteId] = useState<string>("");
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("regression");
  const [maxCases, setMaxCases] = useState<number>(5);
  const [error, setError] = useState<string | null>(null);

  const effectiveSuiteId = selectedSuiteId || (suites.length > 0 ? suites[0].suite_id : "");

  if (!isOpen) return null;

  const currentSuite = suites.find((s) => s.suite_id === effectiveSuiteId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!effectiveSuiteId) return;

    try {
      setError(null);
      await onSubmit({
        suite_id: effectiveSuiteId,
        project_id: currentSuite?.supported_scope === "project" ? currentProjectId : null,
        execution_mode: executionMode,
        max_cases: maxCases,
      });
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to trigger benchmark run";
      setError(msg);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl border border-gray-200 max-w-lg w-full p-6 animate-in fade-in duration-200">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div>
            <h3 className="text-lg font-bold text-gray-900">Execute Benchmark Suite</h3>
            <p className="text-xs text-gray-500 mt-0.5">
              Run automated deterministic evaluation to score model faithfulness &amp; regression metrics.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-5">
          {/* Suite Selector */}
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
              Benchmark Suite
            </label>
            <select
              value={effectiveSuiteId}
              onChange={(e) => setSelectedSuiteId(e.target.value)}
              disabled={isLoading || isViewer}
              className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white"
            >
              {suites.map((s) => (
                <option key={s.suite_id} value={s.suite_id}>
                  {s.name} ({s.target_type} • {s.case_count} cases)
                </option>
              ))}
            </select>
            {currentSuite && (
              <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">
                {currentSuite.description}
              </p>
            )}
          </div>

          {/* Execution Mode */}
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
              Execution Mode
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label
                className={`flex flex-col p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                  executionMode === "regression"
                    ? "border-blue-600 bg-blue-50/50 text-blue-900 ring-1 ring-blue-600"
                    : "border-gray-200 hover:bg-gray-50 text-gray-700"
                }`}
              >
                <div className="flex items-center justify-between font-bold">
                  <span>Regression Mode</span>
                  <input
                    type="radio"
                    name="executionMode"
                    value="regression"
                    checked={executionMode === "regression"}
                    onChange={() => setExecutionMode("regression")}
                    disabled={isLoading || isViewer}
                    className="h-3.5 w-3.5 text-blue-600"
                  />
                </div>
                <span className="text-[11px] text-gray-500 mt-1">
                  Deterministic offline test harness. Fast, cost-free, zero paid API tokens.
                </span>
              </label>

              <label
                className={`flex flex-col p-3 rounded-xl border text-xs cursor-pointer transition-all ${
                  executionMode === "real_provider"
                    ? "border-blue-600 bg-blue-50/50 text-blue-900 ring-1 ring-blue-600"
                    : "border-gray-200 hover:bg-gray-50 text-gray-700"
                }`}
              >
                <div className="flex items-center justify-between font-bold">
                  <span>Real Provider</span>
                  <input
                    type="radio"
                    name="executionMode"
                    value="real_provider"
                    checked={executionMode === "real_provider"}
                    onChange={() => setExecutionMode("real_provider")}
                    disabled={isLoading || isViewer}
                    className="h-3.5 w-3.5 text-blue-600"
                  />
                </div>
                <span className="text-[11px] text-gray-500 mt-1">
                  Evaluates against live production LLM endpoints under 10s per-case timeouts.
                </span>
              </label>
            </div>
          </div>

          {/* Max Cases */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                Evaluation Slice (Max Cases)
              </label>
              <span className="text-xs font-bold font-mono text-gray-900 bg-gray-100 px-2 py-0.5 rounded">
                {maxCases} {maxCases === 1 ? "case" : "cases"}
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={25}
              value={maxCases}
              onChange={(e) => setMaxCases(Number(e.target.value))}
              disabled={isLoading || isViewer}
              className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
            />
            <div className="flex justify-between text-[10px] text-gray-400 mt-1">
              <span>1 (Fast smoke test)</span>
              <span>25 (Full benchmark)</span>
            </div>
          </div>

          {/* Footer Actions */}
          <div className="pt-4 border-t border-gray-100 flex items-center justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isLoading}
              className="px-4 py-2 text-xs font-semibold rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isLoading || isViewer}
              title={isViewer ? "Viewers cannot launch benchmark runs" : undefined}
              className="px-4 py-2 text-xs font-semibold rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-xs transition-colors flex items-center space-x-2"
            >
              {isLoading ? (
                <>
                  <svg className="animate-spin h-3.5 w-3.5 text-white" viewBox="0 0 24 24">
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
                  <span>Launching...</span>
                </>
              ) : (
                <span>Launch Benchmark</span>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
