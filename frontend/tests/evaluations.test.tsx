import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import EvaluationsPage from "@/app/evaluations/page";
import { ProjectContext } from "@/features/projects/ProjectContext";
import { AuthContext } from "@/features/auth/AuthContext";
import { api } from "@/services/apiClient";
import { Project } from "@/types/projects";
import { UserResponse } from "@/types/api";
import { BenchmarkSuiteInfo, EvaluationRun } from "@/types/evaluations";

const mockProject: Project = {
  id: 42,
  name: "Evaluation Workspace",
  description: "Test description",
  owner_id: 1,
  created_at: "2026-10-30T00:00:00Z",
  updated_at: "2026-10-30T00:00:00Z",
};

const mockSuites: BenchmarkSuiteInfo[] = [
  {
    suite_id: "rag_faithfulness",
    name: "RAG Faithfulness & Grounding",
    description: "Evaluates claim grounding and citation precision.",
    target_type: "research",
    supported_scope: "both",
    default_dataset_id: "research_grounding_v1",
    default_dataset_version: "1.0.0",
    case_count: 5,
    metrics: ["citation_precision", "claim_grounding_rate", "rag_faithfulness"],
  },
  {
    suite_id: "coding_ast",
    name: "Coding AST & Syntax Validity",
    description: "Evaluates Python and TypeScript diff applicability and AST.",
    target_type: "developer",
    supported_scope: "system",
    default_dataset_id: "developer_ast_v1",
    default_dataset_version: "1.0.0",
    case_count: 5,
    metrics: ["ast_syntax_validity", "diff_applicability_rate"],
  },
];

const mockBaselineRun: EvaluationRun = {
  id: "run-baseline-001",
  suite_id: "rag_faithfulness",
  dataset_id: "research_grounding_v1",
  dataset_version: "1.0.0",
  dataset_sha256: "sha256_mock_base",
  execution_mode: "regression",
  model_name: "deterministic-test-provider",
  metric_schema_version: "1.0.0",
  target_type: "research",
  status: "completed",
  is_baseline: true,
  total_cases: 5,
  passed_cases: 5,
  failed_cases: 0,
  duration_ms: 150.0,
  summary_metrics: {
    rag_faithfulness: 0.90,
    citation_precision: 0.85,
    ast_syntax_validity: 1.0,
    p95_latency_ms: 150.0,
  },
  created_at: "2026-10-30T10:00:00Z",
  case_results: [],
};

const mockLatestRun: EvaluationRun = {
  id: "run-latest-002",
  suite_id: "rag_faithfulness",
  dataset_id: "research_grounding_v1",
  dataset_version: "1.0.0",
  dataset_sha256: "sha256_mock_latest",
  execution_mode: "regression",
  model_name: "deterministic-test-provider",
  metric_schema_version: "1.0.0",
  target_type: "research",
  status: "completed",
  is_baseline: false,
  total_cases: 5,
  passed_cases: 5,
  failed_cases: 0,
  duration_ms: 120.0,
  summary_metrics: {
    rag_faithfulness: 0.95, // +5% vs baseline
    citation_precision: 0.90, // +5% vs baseline
    ast_syntax_validity: 1.0, // 0.0 vs baseline
    p95_latency_ms: 120.0, // -30ms vs baseline (improved latency!)
  },
  created_at: "2026-10-30T11:00:00Z",
  case_results: [
    {
      id: 1,
      run_id: "run-latest-002",
      case_id: "case_01",
      status: "passed",
      duration_ms: 24.0,
      metrics: { citation_precision: 1.0, claim_grounding_rate: 1.0 },
      failure_reason: null,
      details: null,
    },
  ],
};

describe("Evaluations Dashboard & Automated Benchmarking", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const renderEvaluationsPage = (role: "admin" | "member" | "viewer" = "member") => {
    const mockUser: UserResponse = {
      id: 1,
      email: "evaluator@orchestra.ai",
      role,
      is_active: true,
      created_at: "2026-10-30T00:00:00Z",
    };

    const authValue = {
      user: mockUser,
      status: "authenticated" as const,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refreshUser: vi.fn(),
    };

    const projectValue = {
      projects: [mockProject],
      selectedProject: mockProject,
      loading: false,
      selectProject: vi.fn(),
      createProject: vi.fn(),
      deleteProject: vi.fn(),
      refreshProjects: vi.fn(),
    };

    return render(
      <AuthContext.Provider value={authValue}>
        <ProjectContext.Provider value={projectValue}>
          <EvaluationsPage />
        </ProjectContext.Provider>
      </AuthContext.Provider>
    );
  };

  it("renders honest empty state when zero evaluation runs exist without fake metrics", async () => {
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.includes("/evaluations/benchmarks")) {
        return Promise.resolve(mockSuites);
      }
      if (url.includes("/evaluations/runs")) {
        return Promise.resolve([]);
      }
      return Promise.reject(new Error("Not found"));
    });

    renderEvaluationsPage("member");

    await waitFor(() => {
      expect(screen.getByText(/No evaluation runs recorded/i)).toBeInTheDocument();
    });

    // Zero fake percentages
    expect(screen.queryByText("99.9%")).not.toBeInTheDocument();
    expect(screen.queryByText("100% Guaranteed")).not.toBeInTheDocument();
    expect(screen.getByText("Run your first benchmark suite to evaluate system intelligence and track regression metrics.")).toBeInTheDocument();
  });

  it("renders real metric cards with directional deltas against baseline", async () => {
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.includes("/evaluations/benchmarks")) {
        return Promise.resolve(mockSuites);
      }
      if (url.includes("/evaluations/runs")) {
        return Promise.resolve([mockLatestRun, mockBaselineRun]);
      }
      return Promise.reject(new Error("Not found"));
    });

    renderEvaluationsPage("member");

    await waitFor(() => {
      // 95.0% for faithfulness
      expect(screen.getByText("95.0%")).toBeInTheDocument();
      // 120 ms for latency
      expect(screen.getByText("120 ms")).toBeInTheDocument();
    });

    // Directional deltas:
    // +5.0% vs baseline (faithfulness and citation precision are higher_is_better)
    expect(screen.getAllByText("+5.0% vs baseline").length).toBeGreaterThanOrEqual(1);
    // -30 ms vs baseline (latency is lower_is_better)
    expect(screen.getByText("-30 ms vs baseline")).toBeInTheDocument();
  });

  it("opens RunEvaluationModal and launches benchmark run synchronously", async () => {
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.includes("/evaluations/benchmarks")) {
        return Promise.resolve(mockSuites);
      }
      if (url.includes("/evaluations/runs")) {
        return Promise.resolve([mockBaselineRun]);
      }
      return Promise.reject(new Error("Not found"));
    });

    const postSpy = vi.spyOn(api, "post").mockResolvedValue(mockLatestRun);

    renderEvaluationsPage("admin");

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Run Benchmark/i })).toBeInTheDocument();
    });

    // Open modal
    fireEvent.click(screen.getByRole("button", { name: /Run Benchmark/i }));

    // Modal title should appear
    expect(screen.getByText("Execute Benchmark Suite")).toBeInTheDocument();

    // Click Launch Benchmark
    const launchBtn = screen.getByRole("button", { name: /Launch Benchmark/i });
    fireEvent.click(launchBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        "/evaluations/runs",
        expect.objectContaining({
          suite_id: "rag_faithfulness",
          execution_mode: "regression",
          max_cases: 5,
        })
      );
    });
  });

  it("inspects run details and displays granular case results", async () => {
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.includes("/evaluations/benchmarks")) {
        return Promise.resolve(mockSuites);
      }
      if (url.includes("/evaluations/runs/run-latest-002")) {
        return Promise.resolve(mockLatestRun);
      }
      if (url.includes("/evaluations/runs")) {
        return Promise.resolve([mockLatestRun]);
      }
      return Promise.reject(new Error("Not found"));
    });

    renderEvaluationsPage("member");

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Inspect/i })).toBeInTheDocument();
    });

    // Click inspect
    fireEvent.click(screen.getByRole("button", { name: /Inspect/i }));

    await waitFor(() => {
      expect(screen.getByText(/Run Inspection: rag_faithfulness/i)).toBeInTheDocument();
      expect(screen.getByText("case_01")).toBeInTheDocument();
    });
  });

  it("strictly enforces viewer role lockout on benchmark execution and deletion", async () => {
    vi.spyOn(api, "get").mockImplementation((url: string) => {
      if (url.includes("/evaluations/benchmarks")) {
        return Promise.resolve(mockSuites);
      }
      if (url.includes("/evaluations/runs")) {
        return Promise.resolve([mockLatestRun]);
      }
      return Promise.reject(new Error("Not found"));
    });

    renderEvaluationsPage("viewer");

    await waitFor(() => {
      expect(screen.getByText(/Viewer Role \(Read Only\)/i)).toBeInTheDocument();
    });

    // "Run Benchmark" button should be disabled
    const runButtons = screen.getAllByRole("button", { name: /Run Benchmark/i });
    for (const btn of runButtons) {
      expect(btn).toBeDisabled();
      expect(btn).toHaveAttribute("title", "Viewers cannot launch benchmark runs");
    }

    // "Delete" action in table should be disabled
    const deleteBtn = screen.getByRole("button", { name: /Delete/i });
    expect(deleteBtn).toBeDisabled();
  });
});
