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
    <div className="bg-[#20212B] rounded-xl shadow-xl border border-white/[0.08] overflow-hidden">
      <div className="px-6 py-4 border-b border-white/[0.06] flex items-center justify-between bg-[#15151B]">
        <h3 className="text-sm font-semibold text-[#F8F8FC]">Historical Benchmark Runs</h3>
        <span className="text-xs text-[#929292]">
          Showing {runs.length} {runs.length === 1 ? "run" : "runs"}
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-white/[0.06]">
          <thead className="bg-[#15151B] text-[11px] font-semibold text-[#929292] uppercase tracking-wider">
            <tr>
              <th className="px-6 py-3.5 text-left">Suite / Target</th>
              <th className="px-4 py-3.5 text-left">Status</th>
              <th className="px-4 py-3.5 text-left">Cases Passed</th>
              <th className="px-4 py-3.5 text-left">Duration</th>
              <th className="px-4 py-3.5 text-left">Mode</th>
              <th className="px-4 py-3.5 text-left">Baseline</th>
              <th className="px-4 py-3.5 text-left">Executed At</th>
              <th className="px-6 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-[#20212B] divide-y divide-white/[0.04] text-xs">
            {runs.map((run) => {
              const isActionLoading = actionLoadingId === run.id;
              const formattedDate = new Date(run.created_at).toLocaleString(undefined, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              });

              return (
                <tr key={run.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-3.5">
                    <div className="font-semibold text-[#F8F8FC]">{run.suite_id}</div>
                    <div className="text-[11px] text-[#929292] font-mono">
                      {run.dataset_id} v{run.dataset_version}
                    </div>
                  </td>
                  <td className="px-4 py-3.5">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="font-semibold text-[#F8F8FC]">
                      {run.passed_cases}
                    </span>
                    <span className="text-[#929292] text-xs"> / {run.total_cases}</span>
                  </td>
                  <td className="px-4 py-3.5 text-[#A4A6B8] font-mono text-xs">
                    {run.duration_ms ? `${run.duration_ms.toFixed(0)}ms` : "—"}
                  </td>
                  <td className="px-4 py-3.5 text-xs text-[#A4A6B8] capitalize">
                    {run.execution_mode}
                  </td>
                  <td className="px-4 py-3.5">
                    {run.is_baseline ? (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#5146FF]/20 text-[#8B7CFF] border border-[#5146FF]/30">
                        Active Baseline
                      </span>
                    ) : (
                      <button
                        type="button"
                        disabled={isViewer || isActionLoading || run.status !== "completed"}
                        onClick={() => handleBaseline(run.id)}
                        className="text-xs text-[#929292] hover:text-[#5146FF] disabled:opacity-40 font-medium cursor-pointer"
                      >
                        Set Baseline
                      </button>
                    )}
                  </td>
                  <td className="px-4 py-3.5 text-xs text-[#929292]">
                    {formattedDate}
                  </td>
                  <td className="px-6 py-3.5 text-right space-x-3">
                    <button
                      type="button"
                      onClick={() => onInspect(run)}
                      className="text-xs font-semibold text-[#8B7CFF] hover:text-white transition cursor-pointer"
                    >
                      Inspect
                    </button>
                    <button
                      type="button"
                      disabled={isViewer || isActionLoading}
                      onClick={() => handleDelete(run.id)}
                      className="text-xs font-medium text-rose-400 hover:text-rose-300 disabled:opacity-40 transition cursor-pointer"
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
