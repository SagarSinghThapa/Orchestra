import { EvalStatus } from "@/types/evaluations";

const statusStyles: Record<EvalStatus, string> = {
  passed: "bg-green-100 text-green-800 border-green-200",
  failed: "bg-red-100 text-red-800 border-red-200",
  running: "bg-blue-100 text-blue-800 border-blue-200 animate-pulse",
  pending: "bg-gray-100 text-gray-600 border-gray-200",
  error: "bg-orange-100 text-orange-800 border-orange-200",
};

export function StatusBadge({ status }: { status: EvalStatus }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusStyles[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
