export type TaskType = 'repo_analysis' | 'code_gen' | 'doc_gen';
export type TaskStatus = 'pending' | 'running' | 'success' | 'error';

export interface DeveloperTaskInput {
  task_type: TaskType;
  repo_ref: string;
  params: Record<string, any>;
}

export interface DeveloperTaskOutput {
  result: any;
  artifacts: string[];
  status: TaskStatus;
}

export interface RepositoryAnalysisResult {
  repository: Record<string, any>;
  languages: string[];
  frameworks: string[];
  architecture: Record<string, any>;
  important_files: string[];
  dependencies: string[];
  entry_points: string[];
  modules: string[];
  tests: Record<string, any>;
  risks: string[];
  recommendations: string[];
}

export interface CodingAgentResult {
  summary: string;
  plan: string[];
  files_changed: string[];
  diffs: Record<string, string>;
  validation: Record<string, string>;
  warnings: string[];
}

export interface DocAgentResult {
  document_type: string;
  content: string;
  sources: string[];
  artifact?: string;
  warnings: string[];
}
