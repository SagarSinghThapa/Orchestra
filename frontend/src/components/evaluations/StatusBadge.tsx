import React from "react";
import { EvalStatus } from "@/types/evaluations";

const statusStyles: Record<EvalStatus, string> = {
  completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  failed: "bg-rose-50 text-rose-700 border-rose-200",
  running: "bg-sky-50 text-sky-700 border-sky-200 animate-pulse",
  pending: "bg-gray-100 text-gray-600 border-gray-200",
};

export function StatusBadge({ status }: { status: EvalStatus }) {
  const style = statusStyles[status] || "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${style}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
