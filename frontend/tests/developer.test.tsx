import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CodingAssistantPage from "@/app/developer/coding/page";
import { ProjectContext } from "@/features/projects/ProjectContext";
import { AuthContext } from "@/features/auth/AuthContext";
import { api } from "@/services/apiClient";

import { Project } from "@/types/projects";
import { UserResponse } from "@/types/api";

const mockProject: Project = {
  id: 42,
  name: "Orchestra Core",
  description: "Test description",
  owner_id: 1,
  created_at: "2026-10-30T00:00:00Z",
  updated_at: "2026-10-30T00:00:00Z",
};

describe("Developer Intelligence Two-Stage Preview & Apply Flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const renderCodingAssistant = (role: "admin" | "member" | "viewer" = "member") => {
    const mockUser: UserResponse = {
      id: 1,
      email: "dev@orchestra.ai",
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
          <CodingAssistantPage />
        </ProjectContext.Provider>
      </AuthContext.Provider>
    );
  };

  it("requires stage 1 preview generation before revealing apply actions", () => {
    renderCodingAssistant("member");

    // Initially, only 'Generate Proposal (Preview)' button exists
    expect(screen.getByRole("button", { name: /Generate Proposal/i })).toBeInTheDocument();
    // 'Apply to Workspace' button must NOT exist yet
    expect(screen.queryByRole("button", { name: /Apply to Workspace/i })).toBeNull();
  });

  it("submits mode='preview' and displays diff with AST status on success", async () => {
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({
      status: "success",
      task_type: "code_gen",
      mode: "preview",
      summary: "Added health check endpoint",
      files_analyzed: ["app/main.py"],
      proposed_patches: [
        {
          path: "app/main.py",
          diff: "--- a/app/main.py\n+++ b/app/main.py\n@@ -1 +1,2 @@\n+def health(): return 'ok'",
          validation_status: "valid",
          original_hash: "a".repeat(64),
          new_hash: "b".repeat(64),
          applied: false,
        },
      ],
      warnings: [],
      tool_events: [],
      metadata: {},
    });

    renderCodingAssistant("member");

    const promptInput = screen.getByPlaceholderText(/Describe the feature/i);
    fireEvent.change(promptInput, { target: { value: "Add health check" } });

    const previewBtn = screen.getByRole("button", { name: /Generate Proposal/i });
    fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(postSpy).toHaveBeenCalledWith(
        "/projects/42/developer",
        expect.objectContaining({
          task_type: "code_gen",
          mode: "preview",
          prompt: "Add health check",
        })
      );
    });

    // Review section should now be visible
    expect(screen.getByText("Added health check endpoint")).toBeInTheDocument();
    expect(screen.getByText("AST: valid")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Apply to Workspace/i })).toBeInTheDocument();
  });

  it("disables 'Apply to Workspace' button for users with 'viewer' role", async () => {
    vi.spyOn(api, "post").mockResolvedValue({
      status: "success",
      task_type: "code_gen",
      mode: "preview",
      summary: "Proposal for viewer",
      files_analyzed: [],
      proposed_patches: [
        {
          path: "app/main.py",
          diff: "diff",
          validation_status: "valid",
          original_hash: "a".repeat(64),
          new_hash: "b".repeat(64),
          applied: false,
        },
      ],
      warnings: [],
      tool_events: [],
      metadata: {},
    });

    renderCodingAssistant("viewer");

    const promptInput = screen.getByPlaceholderText(/Describe the feature/i);
    fireEvent.change(promptInput, { target: { value: "Review change" } });

    fireEvent.click(screen.getByRole("button", { name: /Generate Proposal/i }));

    await waitFor(() => {
      expect(screen.getByText("Proposal for viewer")).toBeInTheDocument();
    });

    const applyBtn = screen.getByRole("button", { name: /Apply to Workspace/i });
    expect(applyBtn).toBeDisabled();
    expect(
      screen.getByText(/Viewer role is not authorized to apply code modifications/i)
    ).toBeInTheDocument();
  });

  it("surfaces actionable guidance when stale base hash mismatch occurs", async () => {
    vi.spyOn(api, "post")
      .mockResolvedValueOnce({
        status: "success",
        task_type: "code_gen",
        mode: "preview",
        summary: "Proposal before conflict",
        files_analyzed: [],
        proposed_patches: [
          {
            path: "app/main.py",
            diff: "diff",
            validation_status: "valid",
            original_hash: "a".repeat(64),
            new_hash: "b".repeat(64),
            applied: false,
          },
        ],
        warnings: [],
        tool_events: [],
        metadata: {},
      })
      .mockRejectedValueOnce(new Error("File modified concurrently. Base hash mismatch."));

    renderCodingAssistant("member");

    fireEvent.change(screen.getByPlaceholderText(/Describe the feature/i), {
      target: { value: "Concurrent test" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Generate Proposal/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Apply to Workspace/i })).toBeInTheDocument();
    });

    // Click Apply -> open modal -> confirm
    fireEvent.click(screen.getByRole("button", { name: /Apply to Workspace/i }));
    fireEvent.click(screen.getByRole("button", { name: /Yes, Write to Disk/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/Workspace files were modified concurrently. Base hashes no longer match./i)
      ).toBeInTheDocument();
    });
  });
});
