import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CreateProjectModal } from "@/components/projects/CreateProjectModal";
import * as projectContext from "@/features/projects/ProjectContext";

describe("CreateProjectModal Architecture & Accessibility", () => {
  const mockCreateProject = vi.fn();
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
    mockCreateProject.mockReset();
    mockOnClose.mockReset();

    vi.spyOn(projectContext, "useProject").mockReturnValue({
      projects: [],
      selectedProject: null,
      selectProject: vi.fn(),
      createProject: mockCreateProject,
      deleteProject: vi.fn(),
      refreshProjects: vi.fn(),
      loading: false,
    });
  });

  it("renders into document.body via React portal when isOpen is true", () => {
    render(<CreateProjectModal isOpen={true} onClose={mockOnClose} />);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-labelledby", "create-project-title");
    expect(dialog.parentElement).toBe(document.body);
  });

  it("does not render when isOpen is false", () => {
    render(<CreateProjectModal isOpen={false} onClose={mockOnClose} />);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("validates required project name and calls createProject on submission", async () => {
    mockCreateProject.mockResolvedValueOnce({ id: 10, name: "Neural Engine" });

    render(<CreateProjectModal isOpen={true} onClose={mockOnClose} />);

    const nameInput = screen.getByPlaceholderText(/Distributed Core Refactor/i);
    const descInput = screen.getByPlaceholderText(/Brief summary/i);
    const submitBtn = screen.getByRole("button", { name: "Create Project" });

    // Submit with empty name
    fireEvent.change(nameInput, { target: { value: "   " } });
    fireEvent.click(submitBtn);
    expect(mockCreateProject).not.toHaveBeenCalled();

    // Fill valid name and description
    fireEvent.change(nameInput, { target: { value: "Neural Engine" } });
    fireEvent.change(descInput, { target: { value: "Deep learning engine" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockCreateProject).toHaveBeenCalledWith("Neural Engine", "Deep learning engine");
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it("closes when Escape key is pressed", () => {
    render(<CreateProjectModal isOpen={true} onClose={mockOnClose} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(mockOnClose).toHaveBeenCalled();
  });

  it("closes when backdrop is clicked", () => {
    render(<CreateProjectModal isOpen={true} onClose={mockOnClose} />);
    const backdrop = screen.getByRole("dialog");
    fireEvent.mouseDown(backdrop);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it("renders API errors gracefully in dialog alert container", async () => {
    mockCreateProject.mockRejectedValueOnce(new Error("Project name already exists"));

    render(<CreateProjectModal isOpen={true} onClose={mockOnClose} />);

    const nameInput = screen.getByPlaceholderText(/Distributed Core Refactor/i);
    const submitBtn = screen.getByRole("button", { name: "Create Project" });

    fireEvent.change(nameInput, { target: { value: "Duplicate Name" } });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Project name already exists");
    });
    expect(mockOnClose).not.toHaveBeenCalled();
  });
});

