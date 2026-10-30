import React from "react";
import { MetricDirection } from "@/types/evaluations";

interface MetricCardProps {
  label: string;
  value?: number | null;
  baselineValue?: number | null;
  unit: "%" | "ms" | "ratio" | "count";
  direction: MetricDirection;
  description?: string;
}

export function MetricCard({
  label,
  value,
  baselineValue,
  unit,
  direction,
  description,
}: MetricCardProps) {
  const formatValue = (val: number | null | undefined): string => {
    if (val === null || val === undefined) return "—";
    if (unit === "%") {
      // In backend, percentages like faithfulness or precision may be 0.0-1.0 or 0-100
      const pct = val <= 1.0 && val >= 0.0 ? val * 100 : val;
      return `${pct.toFixed(1)}%`;
    }
    if (unit === "ms") {
      return `${val.toFixed(0)} ms`;
    }
    if (unit === "ratio") {
      return val.toFixed(3);
    }
    return val.toString();
  };

  const calculateDelta = (): {
    text: string;
    isPositiveGood: boolean;
    isNeutral: boolean;
  } | null => {
    if (value === null || value === undefined || baselineValue === null || baselineValue === undefined) {
      return null;
    }

    const diff = value - baselineValue;
    if (Math.abs(diff) < 0.0001) {
      return { text: "0.0 (no change)", isPositiveGood: true, isNeutral: true };
    }

    let formattedDiff = "";
    if (unit === "%") {
      const pctDiff = diff <= 1.0 && diff >= -1.0 ? diff * 100 : diff;
      formattedDiff = `${pctDiff > 0 ? "+" : ""}${pctDiff.toFixed(1)}%`;
    } else if (unit === "ms") {
      formattedDiff = `${diff > 0 ? "+" : ""}${diff.toFixed(0)} ms`;
    } else {
      formattedDiff = `${diff > 0 ? "+" : ""}${diff.toFixed(2)}`;
    }

    // Directional semantics:
    // If higher_is_better: diff > 0 is good (green), diff < 0 is bad (red)
    // If lower_is_better: diff < 0 is good (green), diff > 0 is bad (red)
    const isGood = direction === "higher_is_better" ? diff > 0 : diff < 0;

    return {
      text: `${formattedDiff} vs baseline`,
      isPositiveGood: isGood,
      isNeutral: false,
    };
  };

  const delta = calculateDelta();

  return (
    <div className="bg-white rounded-xl shadow-xs border border-gray-200 p-5 flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            {label}
          </span>
          <span className="text-[10px] text-gray-400 font-mono">
            {direction === "higher_is_better" ? "Target: Higher" : "Target: Lower"}
          </span>
        </div>
        <div className="flex items-baseline mt-2 space-x-2">
          <span className="text-3xl font-extrabold text-gray-900 tracking-tight">
            {formatValue(value)}
          </span>
        </div>
        {description && (
          <p className="text-xs text-gray-500 mt-1 line-clamp-1">{description}</p>
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs">
        {delta ? (
          <div
            className={`flex items-center font-semibold ${
              delta.isNeutral
                ? "text-gray-500"
                : delta.isPositiveGood
                ? "text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full"
                : "text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full"
            }`}
          >
            <span>{delta.text}</span>
          </div>
        ) : (
          <span className="text-gray-400 italic">No baseline delta</span>
        )}
      </div>
    </div>
  );
}
