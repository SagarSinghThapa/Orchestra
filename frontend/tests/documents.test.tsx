import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DocumentsPage, { ALLOWED_EXTENSIONS, MAX_FILE_SIZE } from "@/app/documents/page";
import { ProjectContext } from "@/features/projects/ProjectContext";
import { Project } from "@/types/projects";
import { api } from "@/services/apiClient";

const mockProject: Project = {
  id: 10,
  name: "Document Workspace",
  description: "Test description",
  owner_id: 1,
  created_at: "2026-10-30T00:00:00Z",
  updated_at: "2026-10-30T00:00:00Z",
};

describe("Documents Page & Upload Validation Whitelist", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const renderDocumentsPage = () => {
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
      <ProjectContext.Provider value={projectValue}>
        <DocumentsPage />
      </ProjectContext.Provider>
    );
  };

  it("strictly restricts ALLOWED_EXTENSIONS to backend supported types: .pdf, .txt, .md", () => {
    expect(ALLOWED_EXTENSIONS).toEqual([".pdf", ".txt", ".md"]);

    // Must NOT contain unsupported extensions
    const unsupported = [".docx", ".json", ".csv", ".xlsx", ".pptx", ".html"];
    for (const ext of unsupported) {
      expect((ALLOWED_EXTENSIONS as readonly string[]).includes(ext)).toBe(false);
    }
  });

  it("configures file input accept attribute to match backend whitelist", async () => {
    vi.spyOn(api, "get").mockResolvedValue([]);
    const { container } = renderDocumentsPage();

    await waitFor(() => {
      expect(screen.getByText(/No documents have been ingested/i)).toBeInTheDocument();
    });

    const fileInput = container.querySelector("input[type='file']");
    expect(fileInput).not.toBeNull();
    expect(fileInput?.getAttribute("accept")).toBe(".pdf,.txt,.md");
  });

  it("displays explicit user-facing copy advertising only .pdf, .txt, .md up to 10MB", async () => {
    vi.spyOn(api, "get").mockResolvedValue([]);
    renderDocumentsPage();

    await waitFor(() => {
      expect(
        screen.getByText(/Supported formats: PDF \(\.pdf\), Plain Text \(\.txt\), Markdown \(\.md\) up to 10MB/i)
      ).toBeInTheDocument();
    });
  });

  it("rejects unsupported extensions (.docx, .json, .csv) with client-side error before network call", async () => {
    const getSpy = vi.spyOn(api, "get").mockResolvedValue([]);
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({});
    const { container } = renderDocumentsPage();

    await waitFor(() => {
      expect(getSpy).toHaveBeenCalled();
    });

    const fileInput = container.querySelector("input[type='file']") as HTMLInputElement;

    const unsupportedFiles = [
      new File(["content"], "report.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }),
      new File(["{}"], "data.json", { type: "application/json" }),
      new File(["a,b,c"], "records.csv", { type: "text/csv" }),
    ];

    for (const file of unsupportedFiles) {
      fireEvent.change(fileInput, { target: { files: [file] } });

      await waitFor(() => {
        expect(screen.getByText(/Unsupported file type/i)).toBeInTheDocument();
      });

      // Crucial: No network request may be initiated for unsupported files
      expect(postSpy).not.toHaveBeenCalled();
    }
  });

  it("enforces MAX_FILE_SIZE limit of 10MB (10485760 bytes)", async () => {
    expect(MAX_FILE_SIZE).toBe(10 * 1024 * 1024);

    vi.spyOn(api, "get").mockResolvedValue([]);
    const postSpy = vi.spyOn(api, "post").mockResolvedValue({});
    const { container } = renderDocumentsPage();

    await waitFor(() => {
      expect(screen.getByText(/No documents have been ingested/i)).toBeInTheDocument();
    });

    const fileInput = container.querySelector("input[type='file']") as HTMLInputElement;

    // Create file exceeding 10MB
    const oversizedFile = new File(["a"], "massive.pdf", { type: "application/pdf" });
    Object.defineProperty(oversizedFile, "size", { value: 11 * 1024 * 1024 });

    fireEvent.change(fileInput, { target: { files: [oversizedFile] } });

    await waitFor(() => {
      expect(screen.getByText(/exceeds maximum limit of 10MB/i)).toBeInTheDocument();
    });

    expect(postSpy).not.toHaveBeenCalled();
  });
});
