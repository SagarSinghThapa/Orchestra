export type DeveloperTaskType = "repo_analysis" | "code_gen" | "doc_gen";
export type DeveloperMode = "preview" | "apply";
export type TaskStatus = "success" | "error";

export interface ProposedPatch {
  path: string;
  diff: string;
  validation_status: string;
  original_hash?: string | null;
  new_hash?: string | null;
  applied: boolean;
}

export interface ToolEventRecord {
  tool_name: string;
  target_path?: string | null;
  duration_ms: number;
  status: string;
}

export interface DeveloperRequest {
  task_type: DeveloperTaskType;
  prompt: string;
  target_files?: string[];
  mode: DeveloperMode;
  expected_file_hashes?: Record<string, string>;
  context_hints?: Record<string, string>;
}

export interface DeveloperResponse {
  status: TaskStatus;
  task_type: DeveloperTaskType;
  mode: DeveloperMode;
  summary: string;
  files_analyzed: string[];
  proposed_patches: ProposedPatch[];
  documentation?: string | null;
  warnings: string[];
  tool_events: ToolEventRecord[];
  metadata: Record<string, unknown>;
}

// Legacy helper types for compatibility if referenced
export type TaskType = DeveloperTaskType;

export interface RepositoryAnalysisResult {
  repository: Record<string, unknown>;
  languages: string[];
  frameworks: string[];
  architecture: Record<string, unknown>;
  important_files: string[];
  dependencies: string[];
  entry_points: string[];
  modules: string[];
  tests: Record<string, unknown>;
  risks: string[];
  recommendations: string[];
}
