import { EvaluationRun } from "@/types/evaluations";
import { StatusBadge } from "./StatusBadge";

export function RunTable({ runs }: { runs: EvaluationRun[] }) {
  if (runs.length === 0) {
    return (
      <div className="text-center py-12 border-2 border-dashed border-gray-200 rounded-lg">
        <h3 className="text-lg font-medium text-gray-900 mb-1">No Evaluation Runs</h3>
        <p className="text-gray-500">Evaluation infrastructure has not produced results yet.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Run ID</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Agent</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Benchmark</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Latency</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Started</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-100">
          {runs.map(run => (
            <tr key={run.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3 text-sm font-mono text-blue-600">{run.id.slice(0, 8)}</td>
              <td className="px-4 py-3 text-sm text-gray-900 font-medium">{run.agent}</td>
              <td className="px-4 py-3 text-sm text-gray-600">{run.benchmark}</td>
              <td className="px-4 py-3"><StatusBadge status={run.status} /></td>
              <td className="px-4 py-3 text-sm text-gray-500">{run.duration_ms ? `${run.duration_ms}ms` : '—'}</td>
              <td className="px-4 py-3 text-sm text-gray-400">{new Date(run.started_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
