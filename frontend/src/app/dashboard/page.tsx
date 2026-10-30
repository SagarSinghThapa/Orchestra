"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { useProject } from "@/features/projects/ProjectContext";
import { api } from "@/services/apiClient";
import { LoadingState, EmptyState } from "@/components/ui/StateWrappers";
import { CreateProjectModal } from "@/components/projects/CreateProjectModal";

export default function DashboardPage() {
  const { projects, selectedProject, loading: projectsLoading } = useProject();
  const [sessionCount, setSessionCount] = useState<number | null>(null);
  const [documentCount, setDocumentCount] = useState<number | null>(null);
  const [metricsLoading, setMetricsLoading] = useState<boolean>(false);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const displaySessionCount = selectedProject ? sessionCount ?? 0 : 0;
  const displayDocumentCount = selectedProject ? documentCount ?? 0 : 0;

  useEffect(() => {
    if (!selectedProject) {
      return;
    }

    let active = true;

    const fetchCounts = async () => {
      setMetricsLoading(true);
      try {
        const [sessions, documents] = await Promise.all([
          api.get<unknown[]>(`/sessions/project/${selectedProject.id}`).catch(() => []),
          api.get<unknown[]>(`/projects/${selectedProject.id}/documents`).catch(() => []),
        ]);

        if (active) {
          setSessionCount(Array.isArray(sessions) ? sessions.length : 0);
          setDocumentCount(Array.isArray(documents) ? documents.length : 0);
        }
      } finally {
        if (active) {
          setMetricsLoading(false);
        }
      }
    };

    fetchCounts();

    return () => {
      active = false;
    };
  }, [selectedProject]);

  if (projectsLoading) {
    return <LoadingState message="Loading platform dashboard..." />;
  }

  if (projects.length === 0) {
    return (
      <div className="max-w-2xl mx-auto mt-12">
        <EmptyState
          title="No Projects Yet"
          description="Create your first project workspace to begin uploading documents, running research queries, and managing code."
        />
        <div className="mt-6 flex justify-center">
          <button
            onClick={() => setModalOpen(true)}
            className="rounded bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
          >
            Create First Project
          </button>
        </div>
        <CreateProjectModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            Active Workspace:{" "}
            <span className="font-semibold text-gray-800">
              {selectedProject?.name || "None Selected"}
            </span>
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded border border-gray-300 bg-white px-3 py-1.5 text-xs font-semibold text-gray-700 shadow-sm hover:bg-gray-50"
        >
          + New Project
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-2">
            Your Projects
          </h2>
          <p className="text-gray-900 text-4xl font-bold">{projects.length}</p>
          <p className="text-xs text-gray-400 mt-2">Active engineering workspaces</p>
        </Card>

        <Card>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-2">
            Project Sessions
          </h2>
          <p className="text-gray-900 text-4xl font-bold">
            {metricsLoading ? "..." : displaySessionCount}
          </p>
          <p className="text-xs text-gray-400 mt-2">Interactive multi-agent chat sessions</p>
        </Card>

        <Card>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-2">
            Indexed Documents
          </h2>
          <p className="text-gray-900 text-4xl font-bold">
            {metricsLoading ? "..." : displayDocumentCount}
          </p>
          <p className="text-xs text-gray-400 mt-2">Verified RAG knowledge base chunks</p>
        </Card>
      </div>

      {/* Quick Launch Cards */}
      <div className="mt-8 border-t pt-6">
        <h2 className="text-lg font-bold text-gray-800 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link
            href="/chat"
            className="p-4 rounded-lg border bg-white hover:border-blue-500 hover:shadow-sm transition-all"
          >
            <h3 className="font-semibold text-blue-600">Start Orchestrator Chat →</h3>
            <p className="text-xs text-gray-500 mt-1">
              Engage with Main LangGraph for Q&A, research, or developer tasks.
            </p>
          </Link>
          <Link
            href="/documents"
            className="p-4 rounded-lg border bg-white hover:border-blue-500 hover:shadow-sm transition-all"
          >
            <h3 className="font-semibold text-blue-600">Ingest Documents →</h3>
            <p className="text-xs text-gray-500 mt-1">
              Upload PDF, Markdown, or code files for semantic hybrid vector search.
            </p>
          </Link>
          <Link
            href="/developer"
            className="p-4 rounded-lg border bg-white hover:border-blue-500 hover:shadow-sm transition-all"
          >
            <h3 className="font-semibold text-blue-600">Developer Workspace →</h3>
            <p className="text-xs text-gray-500 mt-1">
              Generate AST-validated patches and examine repository intelligence.
            </p>
          </Link>
        </div>
      </div>

      <CreateProjectModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
