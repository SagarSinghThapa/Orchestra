"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Project, ProjectCreate } from "@/types/projects";
import { api } from "@/services/apiClient";
import { useAuth } from "@/features/auth/AuthContext";

export interface ProjectContextType {
  projects: Project[];
  selectedProject: Project | null;
  loading: boolean;
  selectProject: (id: number) => void;
  createProject: (name: string, description?: string) => Promise<Project>;
  deleteProject: (id: number) => Promise<void>;
  refreshProjects: () => Promise<void>;
}

export const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

const SELECTED_PROJECT_KEY = "orchestra_selected_project_id";

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    let isMounted = true;
    if (status !== "authenticated") {
      return;
    }

    const loadProjects = async () => {
      try {
        const list = await api.get<Project[]>("/projects");
        if (!isMounted) return;
        setProjects(list);

        const storedIdStr =
          typeof window !== "undefined" ? localStorage.getItem(SELECTED_PROJECT_KEY) : null;
        let matched: Project | null = null;
        if (storedIdStr) {
          const parsed = parseInt(storedIdStr, 10);
          if (!isNaN(parsed) && parsed > 0) {
            matched = list.find((p) => p.id === parsed) || null;
          }
        }

        if (matched) {
          setSelectedProject(matched);
        } else if (list.length > 0) {
          setSelectedProject(list[0]);
          if (typeof window !== "undefined") {
            localStorage.setItem(SELECTED_PROJECT_KEY, list[0].id.toString());
          }
        } else {
          setSelectedProject(null);
          if (typeof window !== "undefined") {
            localStorage.removeItem(SELECTED_PROJECT_KEY);
          }
        }
      } catch {
        if (isMounted) {
          setProjects([]);
          setSelectedProject(null);
        }
      }
    };

    loadProjects();

    return () => {
      isMounted = false;
    };
  }, [status]);

  const refreshProjects = useCallback(async () => {
    if (status !== "authenticated") {
      setProjects([]);
      setSelectedProject(null);
      return;
    }

    try {
      setLoading(true);
      const list = await api.get<Project[]>("/projects");
      setProjects(list);

      const storedIdStr =
        typeof window !== "undefined" ? localStorage.getItem(SELECTED_PROJECT_KEY) : null;
      let matched: Project | null = null;
      if (storedIdStr) {
        const parsed = parseInt(storedIdStr, 10);
        if (!isNaN(parsed) && parsed > 0) {
          matched = list.find((p) => p.id === parsed) || null;
        }
      }

      if (matched) {
        setSelectedProject(matched);
      } else if (list.length > 0) {
        setSelectedProject(list[0]);
        if (typeof window !== "undefined") {
          localStorage.setItem(SELECTED_PROJECT_KEY, list[0].id.toString());
        }
      } else {
        setSelectedProject(null);
        if (typeof window !== "undefined") {
          localStorage.removeItem(SELECTED_PROJECT_KEY);
        }
      }
    } catch {
      setProjects([]);
      setSelectedProject(null);
    } finally {
      setLoading(false);
    }
  }, [status]);

  const selectProject = (id: number) => {
    const found = projects.find((p) => p.id === id);
    if (found) {
      setSelectedProject(found);
      if (typeof window !== "undefined") {
        localStorage.setItem(SELECTED_PROJECT_KEY, found.id.toString());
      }
    }
  };

  const createProject = async (name: string, description?: string): Promise<Project> => {
    const payload: ProjectCreate = { name, description };
    const created = await api.post<Project>("/projects", payload);
    setProjects((prev) => [created, ...prev]);
    setSelectedProject(created);
    if (typeof window !== "undefined") {
      localStorage.setItem(SELECTED_PROJECT_KEY, created.id.toString());
    }
    return created;
  };

  const deleteProject = async (id: number): Promise<void> => {
    await api.delete(`/projects/${id}`);
    setProjects((prev) => prev.filter((p) => p.id !== id));
    if (selectedProject?.id === id) {
      const remaining = projects.filter((p) => p.id !== id);
      const nextSelected = remaining.length > 0 ? remaining[0] : null;
      setSelectedProject(nextSelected);
      if (typeof window !== "undefined") {
        if (nextSelected) {
          localStorage.setItem(SELECTED_PROJECT_KEY, nextSelected.id.toString());
        } else {
          localStorage.removeItem(SELECTED_PROJECT_KEY);
        }
      }
    }
  };

  return (
    <ProjectContext.Provider
      value={{
        projects,
        selectedProject,
        loading,
        selectProject,
        createProject,
        deleteProject,
        refreshProjects,
      }}
    >
      {children}
    </ProjectContext.Provider>
  );
}

export function useProject(): ProjectContextType {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error("useProject must be used within a ProjectProvider");
  }
  return context;
}
