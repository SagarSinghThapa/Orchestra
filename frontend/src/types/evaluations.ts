/**
 * PROVISIONAL EVALUATION TYPES
 * 
 * These interfaces are provisional adapters for the Evaluation Dashboard UI.
 * Member 1 owns evaluation metrics/benchmarks/datasets.
 * Member 2 owns evaluation execution infrastructure.
 * Member 3 owns ONLY the dashboard/UI rendering.
 * 
 * These types MUST be updated once M1/M2 publish their evaluation contracts.
 */

export type EvalStatus = 'passed' | 'failed' | 'running' | 'pending' | 'error';

export interface EvaluationMetric {
  name: string;
  value: number;
  unit: string;
  trend?: 'up' | 'down' | 'stable';
}

export interface EvaluationRun {
  id: string;
  agent: string;
  benchmark: string;
  status: EvalStatus;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
  metrics: EvaluationMetric[];
  failure_reason?: string;
}

export interface AgentPerformance {
  agent: string;
  total_runs: number;
  passed: number;
  failed: number;
  avg_latency_ms: number;
  success_rate: number;
}

export interface BenchmarkResult {
  benchmark: string;
  runs: number;
  avg_score: number;
  best_score: number;
  worst_score: number;
}

export interface EvaluationSummary {
  total_runs: number;
  passed: number;
  failed: number;
  running: number;
  pending: number;
  agents: AgentPerformance[];
  benchmarks: BenchmarkResult[];
  recent_runs: EvaluationRun[];
  metrics: EvaluationMetric[];
}

export interface EvaluationFilters {
  agent?: string;
  benchmark?: string;
  status?: EvalStatus;
  date_from?: string;
  date_to?: string;
}
