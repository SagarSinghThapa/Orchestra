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
    return (
      <div className="p-8 workspace-gradient-bg min-h-[calc(100vh-3.5rem)]">
        <LoadingState message="Loading platform dashboard..." />
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className="p-8 workspace-gradient-bg min-h-[calc(100vh-3.5rem)]">
        <div className="max-w-2xl mx-auto mt-12">
          <EmptyState
            title="No Projects Yet"
            description="Create your first project workspace to begin uploading documents, running research queries, and managing code."
          />
          <div className="mt-6 flex justify-center">
            <button
              onClick={() => setModalOpen(true)}
              className="rounded-xl bg-[#5146FF] hover:bg-[#4338e8] px-5 py-2.5 text-xs font-semibold text-white shadow-sm transition active:scale-95 cursor-pointer"
            >
              Create First Project
            </button>
          </div>
          <CreateProjectModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 sm:p-8 space-y-6 max-w-6xl mx-auto pb-12">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#F8F8FC] tracking-tight">Dashboard</h1>
          <p className="text-xs sm:text-sm text-[#A4A6B8] mt-1">
            Active Workspace:{" "}
            <span className="font-semibold text-[#F8F8FC]">
              {selectedProject?.name || "None Selected"}
            </span>
          </p>
        </div>
        <button
          onClick={() => setModalOpen(true)}
          className="rounded-xl bg-[#5146FF] hover:bg-[#4338e8] px-4 py-2 text-xs font-semibold text-white shadow-sm transition active:scale-95 cursor-pointer"
        >
          + New Project
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card>
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[#929292] mb-2">
            Your Projects
          </h2>
          <p className="text-[#F8F8FC] text-4xl font-extrabold tracking-tight">{projects.length}</p>
          <p className="text-xs text-[#929292] mt-2">Active engineering workspaces</p>
        </Card>

        <Card>
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[#929292] mb-2">
            Project Sessions
          </h2>
          <p className="text-[#F8F8FC] text-4xl font-extrabold tracking-tight">
            {metricsLoading ? "..." : displaySessionCount}
          </p>
          <p className="text-xs text-[#929292] mt-2">Interactive multi-agent chat sessions</p>
        </Card>

        <Card>
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-[#929292] mb-2">
            Indexed Documents
          </h2>
          <p className="text-[#F8F8FC] text-4xl font-extrabold tracking-tight">
            {metricsLoading ? "..." : displayDocumentCount}
          </p>
          <p className="text-xs text-[#929292] mt-2">Verified RAG knowledge base chunks</p>
        </Card>
      </div>

      {/* Quick Launch Cards */}
      <div className="mt-8 border-t border-white/[0.06] pt-6">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-[#929292] mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link
            href="/chat"
            className="p-5 rounded-xl bg-[#20212B] border border-white/[0.08] hover:border-white/20 hover:bg-[#242634] shadow-xl transition-all group"
          >
            <div className="w-8 h-8 rounded-lg bg-[#5146FF]/15 flex items-center justify-center mb-3">
              <svg className="w-4 h-4 text-[#8B7CFF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
            </div>
            <h3 className="font-semibold text-xs sm:text-sm text-[#F8F8FC] group-hover:text-[#8B7CFF] transition-colors">Start Orchestrator Chat →</h3>
            <p className="text-xs text-[#A4A6B8] mt-1.5 leading-relaxed">
              Engage with Main LangGraph for Q&amp;A, research, or developer tasks.
            </p>
          </Link>

          <Link
            href="/documents"
            className="p-5 rounded-xl bg-[#20212B] border border-white/[0.08] hover:border-white/20 hover:bg-[#242634] shadow-xl transition-all group"
          >
            <div className="w-8 h-8 rounded-lg bg-[#5146FF]/15 flex items-center justify-center mb-3">
              <svg className="w-4 h-4 text-[#5146FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="font-semibold text-xs sm:text-sm text-[#F8F8FC] group-hover:text-[#8B7CFF] transition-colors">Ingest Documents →</h3>
            <p className="text-xs text-[#A4A6B8] mt-1.5 leading-relaxed">
              Upload PDF, Markdown, or code files for semantic hybrid vector search.
            </p>
          </Link>

          <Link
            href="/developer/coding"
            className="p-5 rounded-xl bg-[#20212B] border border-white/[0.08] hover:border-white/20 hover:bg-[#242634] shadow-xl transition-all group"
          >
            <div className="w-8 h-8 rounded-lg bg-[#8B7CFF]/15 flex items-center justify-center mb-3">
              <svg className="w-4 h-4 text-[#8B7CFF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
            </div>
            <h3 className="font-semibold text-xs sm:text-sm text-[#F8F8FC] group-hover:text-[#8B7CFF] transition-colors">Developer Workspace →</h3>
            <p className="text-xs text-[#A4A6B8] mt-1.5 leading-relaxed">
              Generate AST-validated patches and examine repository intelligence.
            </p>
          </Link>
        </div>
      </div>

      <CreateProjectModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
    </div>
  );
}
