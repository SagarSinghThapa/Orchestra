import { DeveloperTaskOutput, TaskStatus } from "@/types/developer";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

class ApiAdapter {
  async request(endpoint: string, options: RequestInit = {}) {
    const token = typeof window !== 'undefined' ? localStorage.getItem("jwt_token") : null;
    
    const headers = {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    };
    
    // Mock Mode check
    if (process.env.NEXT_PUBLIC_USE_MOCK_API === 'true') {
      console.log(`[Mock API Request]: ${endpoint}`, options.body);
      return this._handleMock(endpoint, options);
    }
    
    try {
      const response = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers });
      if (!response.ok) {
        throw new Error(`API Error: ${response.statusText}`);
      }
      return response.json();
    } catch (error) {
      console.error(error);
      throw error;
    }
  }

  get(endpoint: string) {
    return this.request(endpoint, { method: "GET" });
  }

  post(endpoint: string, data: any) {
    return this.request(endpoint, { method: "POST", body: JSON.stringify(data) });
  }

  // Temporary mock handler for Developer Tasks
  private async _handleMock(endpoint: string, options: RequestInit): Promise<any> {
    await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate latency
    
    if (endpoint === '/developer/task' && options.body) {
      const body = JSON.parse(options.body as string);
      
      const output: DeveloperTaskOutput = {
        status: 'success',
        artifacts: [],
        result: {}
      };

      if (body.task_type === 'repo_analysis') {
        output.result = {
          repository: { size: "1.2MB", files: 124 },
          languages: ["TypeScript", "Python"],
          frameworks: ["Next.js", "FastAPI"],
          architecture: { inferred: "Microservices with Agentic Subgraphs" },
          important_files: ["package.json", "main.py"],
          dependencies: ["react", "langgraph"],
          entry_points: ["src/app/layout.tsx", "backend/main.py"],
          modules: ["frontend", "backend"],
          tests: { coverage: "80%" },
          risks: ["Missing env configurations in mock mode."],
          recommendations: ["Ensure API adapter is connected."]
        };
      } 
      else if (body.task_type === 'code_gen') {
        output.result = {
          summary: `Successfully generated ${body.params?.mode === 'apply' ? 'and applied' : '(preview)'} changes.`,
          plan: ["Understand context", "Write code", "Validate AST"],
          files_changed: ["src/components/ui/Button.tsx"],
          diffs: {
            "src/components/ui/Button.tsx": "@@ -1,5 +1,6 @@\n+ // Optimized\n export function Button"
          },
          validation: {
            "src/components/ui/Button.tsx": "Valid"
          },
          warnings: []
        };
        if (body.params?.mode === 'apply') output.artifacts = ["src/components/ui/Button.tsx"];
      }
      else if (body.task_type === 'doc_gen') {
        output.result = {
          document_type: body.params?.doc_type || 'README',
          content: `# ${body.params?.doc_type || 'README'}\n\nGenerated from mock context.`,
          sources: ["src/app/layout.tsx", "package.json"],
          artifact: body.params?.mode === 'apply' ? `docs/${body.params?.doc_type}.md` : undefined,
          warnings: []
        };
        if (body.params?.mode === 'apply') output.artifacts = [`docs/${body.params?.doc_type}.md`];
      }

      return { output_payload: output, trace_id: `trace-mock-${Date.now()}` };
    }

    if (endpoint === '/evaluations/summary') {
      return {
        total_runs: 47,
        passed: 38,
        failed: 6,
        running: 2,
        pending: 1,
        metrics: [
          { name: "Avg Latency", value: 342, unit: "ms", trend: "down" as const },
          { name: "Success Rate", value: 80.9, unit: "%", trend: "up" as const },
          { name: "Total Runs", value: 47, unit: "runs", trend: "up" as const },
          { name: "Active Benchmarks", value: 3, unit: "", trend: "stable" as const },
        ],
        agents: [
          { agent: "Repository Agent", total_runs: 20, passed: 18, failed: 2, avg_latency_ms: 280, success_rate: 0.90 },
          { agent: "Coding Agent", total_runs: 15, passed: 12, failed: 3, avg_latency_ms: 410, success_rate: 0.80 },
          { agent: "Documentation Agent", total_runs: 12, passed: 8, failed: 1, avg_latency_ms: 190, success_rate: 0.73 },
        ],
        benchmarks: [
          { benchmark: "Code Quality", runs: 15, avg_score: 82.3, best_score: 96, worst_score: 54 },
          { benchmark: "Doc Accuracy", runs: 12, avg_score: 78.1, best_score: 92, worst_score: 61 },
          { benchmark: "Repo Analysis", runs: 20, avg_score: 91.7, best_score: 99, worst_score: 72 },
        ],
        recent_runs: [
          { id: "run-a1b2c3d4", agent: "Repository Agent", benchmark: "Repo Analysis", status: "passed" as const, started_at: "2026-09-05T14:30:00Z", duration_ms: 245, metrics: [], },
          { id: "run-e5f6g7h8", agent: "Coding Agent", benchmark: "Code Quality", status: "failed" as const, started_at: "2026-09-05T14:15:00Z", duration_ms: 520, metrics: [], failure_reason: "AST validation failed on generated output" },
          { id: "run-i9j0k1l2", agent: "Documentation Agent", benchmark: "Doc Accuracy", status: "passed" as const, started_at: "2026-09-05T13:45:00Z", duration_ms: 180, metrics: [], },
          { id: "run-m3n4o5p6", agent: "Coding Agent", benchmark: "Code Quality", status: "running" as const, started_at: "2026-09-05T15:00:00Z", metrics: [], },
          { id: "run-q7r8s9t0", agent: "Repository Agent", benchmark: "Repo Analysis", status: "passed" as const, started_at: "2026-09-05T12:00:00Z", duration_ms: 310, metrics: [], },
        ],
      };
    }

    return { success: true, mocked: true };
  }
}

export const api = new ApiAdapter();
