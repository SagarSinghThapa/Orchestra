export type EvalStatus = 'pending' | 'running' | 'completed' | 'failed';
export type CaseStatus = 'passed' | 'failed' | 'error' | 'skipped';
export type ExecutionMode = 'regression' | 'real_provider';
export type MetricDirection = 'higher_is_better' | 'lower_is_better';

export interface EvaluationCaseResult {
  id: number;
  run_id: string;
  case_id: string;
  status: CaseStatus;
  duration_ms: number;
  metrics: Record<string, number>;
  failure_reason?: string | null;
  details?: Record<string, unknown> | null;
}

export interface EvaluationRun {
  id: string;
  project_id?: number | null;
  created_by_user_id?: number | null;
  suite_id: string;
  dataset_id: string;
  dataset_version: string;
  dataset_sha256: string;
  execution_mode: ExecutionMode;
  model_name: string;
  metric_schema_version: string;
  target_type: string;
  status: EvalStatus;
  is_baseline: boolean;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  duration_ms: number;
  summary_metrics: Record<string, number>;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
  case_results?: EvaluationCaseResult[];
}

export interface BenchmarkSuiteInfo {
  suite_id: string;
  name: string;
  description: string;
  target_type: string;
  supported_scope: 'system' | 'project' | 'both';
  default_dataset_id: string;
  default_dataset_version: string;
  case_count: number;
  metrics: string[];
}

export interface EvaluationRunCreate {
  suite_id: string;
  project_id?: number | null;
  execution_mode: ExecutionMode;
  max_cases?: number;
}
