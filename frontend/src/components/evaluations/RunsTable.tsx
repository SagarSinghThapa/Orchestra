import React from "react";
import { EvaluationRun } from "@/types/evaluations";
import { StatusBadge } from "./StatusBadge";

interface RunsTableProps {
  runs: EvaluationRun[];
  isViewer: boolean;
  onInspect: (run: EvaluationRun) => void;
  onSetBaseline: (runId: string) => Promise<void>;
  onDelete: (runId: string) => Promise<void>;
}

export function RunsTable({
  runs,
  isViewer,
  onInspect,
  onSetBaseline,
  onDelete,
}: RunsTableProps) {
  const [actionLoadingId, setActionLoadingId] = React.useState<string | null>(null);

  const handleBaseline = async (id: string) => {
    try {
      setActionLoadingId(id);
      await onSetBaseline(id);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this evaluation run?")) {
      return;
    }
    try {
      setActionLoadingId(id);
      await onDelete(id);
    } finally {
      setActionLoadingId(null);
    }
  };

  if (runs.length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-xl shadow-xs border border-gray-200 overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-base font-bold text-gray-900">Historical Benchmark Runs</h3>
        <span className="text-xs text-gray-500 font-medium">
          Showing {runs.length} {runs.length === 1 ? "run" : "runs"}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50 text-[11px] font-bold text-gray-500 uppercase tracking-wider">
            <tr>
              <th className="px-5 py-3 text-left">Suite / Target</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left">Cases Passed</th>
              <th className="px-4 py-3 text-left">Duration</th>
              <th className="px-4 py-3 text-left">Mode</th>
              <th className="px-4 py-3 text-left">Baseline</th>
              <th className="px-4 py-3 text-left">Executed At</th>
              <th className="px-5 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-100 text-sm">
            {runs.map((run) => {
              const isActionLoading = actionLoadingId === run.id;
              const formattedDate = new Date(run.created_at).toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              });

              return (
                <tr key={run.id} className="hover:bg-gray-50/70 transition-colors">
                  <td className="px-5 py-3.5">
                    <div className="font-semibold text-gray-900">{run.suite_id}</div>
                    <div className="text-xs text-gray-400 font-mono">
                      {run.dataset_id} v{run.dataset_version}
                    </div>
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="font-semibold text-gray-900">
                      {run.passed_cases}
                    </span>
                    <span className="text-gray-400 text-xs"> / {run.total_cases}</span>
                  </td>
                  <td className="px-4 py-3.5 text-gray-600 font-mono text-xs">
                    {run.duration_ms ? `${run.duration_ms.toFixed(0)}ms` : "—"}
                  </td>
                  <td className="px-4 py-3.5 text-xs text-gray-600 capitalize">
                    {run.execution_mode}
                  </td>
                  <td className="px-4 py-3.5">
                    {run.is_baseline ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200">
                        ★ Active Baseline
                      </span>
                    ) : (
                      <span className="text-gray-400 text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3.5 text-xs text-gray-500 whitespace-nowrap">
                    {formattedDate}
                  </td>
                  <td className="px-5 py-3.5 text-right space-x-2 whitespace-nowrap">
                    <button
                      type="button"
                      onClick={() => onInspect(run)}
                      className="px-2.5 py-1 text-xs font-semibold rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      Inspect
                    </button>
                    {!run.is_baseline && (
                      <button
                        type="button"
                        disabled={isViewer || isActionLoading}
                        onClick={() => handleBaseline(run.id)}
                        title={isViewer ? "Viewers cannot modify baselines" : "Promote to baseline"}
                        className="px-2.5 py-1 text-xs font-semibold rounded-md border border-amber-300 text-amber-800 hover:bg-amber-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        Set Baseline
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={isViewer || isActionLoading}
                      onClick={() => handleDelete(run.id)}
                      title={isViewer ? "Viewers cannot delete runs" : "Delete run"}
                      className="px-2.5 py-1 text-xs font-semibold rounded-md border border-rose-200 text-rose-700 hover:bg-rose-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Re-export alias for backward compatibility
export const RunTable = RunsTable;
