import { EvaluationMetric } from "@/types/evaluations";

export function MetricCard({ metric }: { metric: EvaluationMetric }) {
  const trendIcon = metric.trend === 'up' ? '↑' : metric.trend === 'down' ? '↓' : '→';
  const trendColor = metric.trend === 'up' ? 'text-green-600' : metric.trend === 'down' ? 'text-red-600' : 'text-gray-400';

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-5">
      <p className="text-sm text-gray-500 uppercase tracking-wide">{metric.name}</p>
      <div className="flex items-baseline mt-2 space-x-2">
        <span className="text-3xl font-bold text-gray-900">
          {typeof metric.value === 'number' ? metric.value.toFixed(1) : metric.value}
        </span>
        <span className="text-sm text-gray-400">{metric.unit}</span>
        {metric.trend && (
          <span className={`text-sm font-semibold ${trendColor}`}>{trendIcon}</span>
        )}
      </div>
    </div>
  );
}
