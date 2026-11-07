import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import ProjectsPage from "@/app/projects/page";
import { ProjectContext, ProjectContextType } from "@/features/projects/ProjectContext";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

// Mock CreateProjectModal
vi.mock("@/components/projects/CreateProjectModal", () => ({
  CreateProjectModal: ({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) =>
    isOpen ? (
      <div data-testid="mock-create-modal">
        <button onClick={onClose}>Close Modal</button>
      </div>
    ) : null,
}));

describe("ProjectsPage UI & Interaction Tests", () => {
  const mockProjects = [
    {
      id: 33,
      name: "Orchestra NVIDIA Demo",
      description: "Grounded RAG workspace with Nemotron",
      owner_id: 1,
      created_at: "2026-10-31T20:00:00Z",
      updated_at: "2026-10-31T20:00:00Z",
    },
    {
      id: 19,
      name: "linkedin automation",
      description: null,
      owner_id: 1,
      created_at: "2026-10-25T12:00:00Z",
      updated_at: "2026-10-25T12:00:00Z",
    },
  ];

  const defaultContextValue: ProjectContextType = {
    projects: mockProjects,
    selectedProject: mockProjects[0],
    loading: false,
    selectProject: vi.fn(),
    createProject: vi.fn(),
    deleteProject: vi.fn(),
    refreshProjects: vi.fn(),
  };

  const renderWithContext = (contextValue = defaultContextValue) => {
    return render(
      <ProjectContext.Provider value={contextValue}>
        <ProjectsPage />
      </ProjectContext.Provider>
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders page header and project cards with authentic metadata", () => {
    renderWithContext();

    expect(screen.getByRole("heading", { name: "Project Workspaces", level: 1 })).toBeInTheDocument();
    expect(screen.getByText("2 Workspaces")).toBeInTheDocument();

    // Verify Project 1 (Active)
    expect(screen.getByText("Orchestra NVIDIA Demo")).toBeInTheDocument();
    expect(screen.getByText("Grounded RAG workspace with Nemotron")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();

    // Verify Project 2 (Null description fallback)
    expect(screen.getByText("linkedin automation")).toBeInTheDocument();
    expect(screen.getByText("No description provided.")).toBeInTheDocument();
  });

  it("clicking Open Workspace selects project and navigates to /chat", () => {
    renderWithContext();

    const openButtons = screen.getAllByRole("button", { name: /Open Workspace/i });
    expect(openButtons.length).toBe(2);

    // Click on second project
    fireEvent.click(openButtons[1]);

    expect(defaultContextValue.selectProject).toHaveBeenCalledWith(19);
    expect(mockPush).toHaveBeenCalledWith("/chat");
  });

  it("clicking the project card container also selects and navigates to /chat", () => {
    renderWithContext();

    const cards = screen.getAllByTestId("project-card");
    expect(cards.length).toBe(2);

    fireEvent.click(cards[1]);
    expect(defaultContextValue.selectProject).toHaveBeenCalledWith(19);
    expect(mockPush).toHaveBeenCalledWith("/chat");
  });

  it("renders loading state when loading and projects list is empty", () => {
    renderWithContext({
      ...defaultContextValue,
      projects: [],
      selectedProject: null,
      loading: true,
    });

    expect(screen.getByText("Loading your project workspaces...")).toBeInTheDocument();
  });

  it("renders empty state with creation CTA when user has zero projects", () => {
    renderWithContext({
      ...defaultContextValue,
      projects: [],
      selectedProject: null,
      loading: false,
    });

    expect(screen.getByText("No projects yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Create Your First Project/i })).toBeInTheDocument();
  });

  it("clicking + New Project opens CreateProjectModal", () => {
    renderWithContext();

    expect(screen.queryByTestId("mock-create-modal")).not.toBeInTheDocument();

    const newProjectBtn = screen.getByRole("button", { name: /\+ New Project/i });
    fireEvent.click(newProjectBtn);

    expect(screen.getByTestId("mock-create-modal")).toBeInTheDocument();

    // Close modal
    fireEvent.click(screen.getByRole("button", { name: "Close Modal" }));
    expect(screen.queryByTestId("mock-create-modal")).not.toBeInTheDocument();
  });
});

