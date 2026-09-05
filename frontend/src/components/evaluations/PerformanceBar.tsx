import { AgentPerformance } from "@/types/evaluations";

export function PerformanceBar({ agent }: { agent: AgentPerformance }) {
  const rate = Math.round(agent.success_rate * 100);
  const barColor = rate >= 80 ? 'bg-green-500' : rate >= 50 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div className="flex items-center space-x-4 py-2">
      <span className="w-40 text-sm font-medium text-gray-700 truncate">{agent.agent}</span>
      <div className="flex-1 bg-gray-200 rounded-full h-3 overflow-hidden">
        <div className={`${barColor} h-3 rounded-full transition-all duration-500`} style={{ width: `${rate}%` }} />
      </div>
      <span className="w-12 text-sm text-right font-semibold text-gray-900">{rate}%</span>
      <span className="w-20 text-xs text-gray-400 text-right">{agent.avg_latency_ms}ms avg</span>
    </div>
  );
}
