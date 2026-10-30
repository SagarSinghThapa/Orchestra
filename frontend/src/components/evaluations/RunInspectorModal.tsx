import React, { useState } from "react";
import { EvaluationRun } from "@/types/evaluations";
import { StatusBadge } from "./StatusBadge";

interface RunInspectorModalProps {
  run: EvaluationRun | null;
  isOpen: boolean;
  onClose: () => void;
}

export function RunInspectorModal({ run, isOpen, onClose }: RunInspectorModalProps) {
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  if (!isOpen || !run) return null;

  const caseResults = run.case_results || [];

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl border border-gray-200 max-w-4xl w-full max-h-[90vh] flex flex-col animate-in fade-in duration-200">
        {/* Header */}
        <div className="px-6 py-5 border-b border-gray-100 flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-3">
            <h3 className="text-lg font-bold text-gray-900">
              Run Inspection: {run.suite_id}
            </h3>
            <StatusBadge status={run.status} />
            {run.is_baseline && (
              <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200">
                ★ Active Baseline
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Scrollable Content */}
        <div className="px-6 py-5 overflow-y-auto space-y-6">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 rounded-xl bg-gray-50 border border-gray-200 text-xs">
            <div>
              <span className="text-gray-400 font-medium block mb-0.5">Run ID</span>
              <span className="font-mono text-gray-800 font-semibold truncate block" title={run.id}>
                {run.id}
              </span>
            </div>
            <div>
              <span className="text-gray-400 font-medium block mb-0.5">Git Commit SHA</span>
              <span className="font-mono text-gray-800 font-semibold truncate block" title={run.metric_schema_version}>
                {run.target_type}
              </span>
            </div>
            <div>
              <span className="text-gray-400 font-medium block mb-0.5">Model / Harness</span>
              <span className="font-semibold text-gray-800 truncate block" title={run.model_name}>
                {run.model_name}
              </span>
            </div>
            <div>
              <span className="text-gray-400 font-medium block mb-0.5">Total Duration</span>
              <span className="font-mono font-semibold text-gray-800 block">
                {run.duration_ms ? `${run.duration_ms.toFixed(0)} ms` : "—"}
              </span>
            </div>
          </div>

          {/* Error Message if run failed */}
          {run.error_message && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
              <span className="font-bold block mb-1">Execution Failure:</span>
              <p className="font-mono">{run.error_message}</p>
            </div>
          )}

          {/* Summary Metrics */}
          <div>
            <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-3">
              Aggregated Summary Metrics
            </h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {Object.entries(run.summary_metrics || {}).map(([metricKey, metricVal]) => (
                <div
                  key={metricKey}
                  className="p-3 bg-white border border-gray-200 rounded-lg shadow-2xs"
                >
                  <span className="text-[11px] font-semibold text-gray-500 block truncate" title={metricKey}>
                    {metricKey.replace(/_/g, " ")}
                  </span>
                  <span className="text-lg font-bold text-gray-900 mt-1 block">
                    {typeof metricVal === "number"
                      ? metricKey.includes("ms")
                        ? `${metricVal.toFixed(0)} ms`
                        : metricVal <= 1.0 && metricVal >= 0.0
                        ? `${(metricVal * 100).toFixed(1)}%`
                        : metricVal.toFixed(2)
                      : String(metricVal)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Granular Case Breakdown */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                Case-by-Case Execution Results ({run.passed_cases} passed, {run.failed_cases} failed)
              </h4>
            </div>

            {caseResults.length === 0 ? (
              <p className="text-xs text-gray-400 italic">No granular case results attached to this run.</p>
            ) : (
              <div className="border border-gray-200 rounded-xl overflow-hidden divide-y divide-gray-200">
                {caseResults.map((caseItem) => {
                  const isExpanded = selectedCaseId === caseItem.case_id;
                  const isPassed = caseItem.status === "passed";

                  return (
                    <div key={caseItem.case_id} className="bg-white">
                      <div
                        onClick={() => setSelectedCaseId(isExpanded ? null : caseItem.case_id)}
                        className="px-4 py-3 flex items-center justify-between cursor-pointer hover:bg-gray-50 transition-colors"
                      >
                        <div className="flex items-center space-x-3">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold ${
                              isPassed
                                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                                : "bg-rose-50 text-rose-700 border border-rose-200"
                            }`}
                          >
                            {caseItem.status.toUpperCase()}
                          </span>
                          <span className="font-mono text-xs font-semibold text-gray-900">
                            {caseItem.case_id}
                          </span>
                        </div>
                        <div className="flex items-center space-x-4 text-xs text-gray-500">
                          <span className="font-mono">{caseItem.duration_ms.toFixed(0)} ms</span>
                          <span className="text-gray-400">{isExpanded ? "▲" : "▼"}</span>
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {isExpanded && (
                        <div className="px-4 py-3 bg-gray-50/70 border-t border-gray-100 text-xs space-y-3">
                          {caseItem.failure_reason && (
                            <div className="p-2.5 rounded bg-rose-50 border border-rose-200 text-rose-800">
                              <span className="font-semibold block mb-0.5">Failure Reason:</span>
                              <pre className="font-mono text-[11px] whitespace-pre-wrap">
                                {caseItem.failure_reason}
                              </pre>
                            </div>
                          )}

                          <div>
                            <span className="font-semibold text-gray-600 block mb-1">
                              Case Metrics:
                            </span>
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                              {Object.entries(caseItem.metrics || {}).map(([k, v]) => (
                                <div key={k} className="p-2 bg-white rounded border border-gray-200">
                                  <span className="text-[10px] text-gray-400 block">{k}</span>
                                  <span className="font-mono font-bold text-gray-800">
                                    {typeof v === "number" ? v.toFixed(3) : String(v)}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>

                          {caseItem.details && (
                            <div>
                              <span className="font-semibold text-gray-600 block mb-1">
                                Diagnostics:
                              </span>
                              <pre className="p-2.5 bg-gray-900 text-gray-100 rounded text-[11px] font-mono overflow-x-auto">
                                {JSON.stringify(caseItem.details, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 flex justify-end shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-gray-900 text-white hover:bg-gray-800 transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
}
