"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useProject } from "@/features/projects/ProjectContext";
import { CreateProjectModal } from "@/components/projects/CreateProjectModal";
import { LoadingState, ErrorState } from "@/components/ui/StateWrappers";

export default function ProjectsPage() {
  const router = useRouter();
  const {
    projects,
    selectedProject,
    selectProject,
    loading,
    refreshProjects,
    deleteProject,
  } = useProject();

  const [modalOpen, setModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const handleOpenWorkspace = (projectId: number) => {
    selectProject(projectId);
    router.push("/chat");
  };

  const handleDelete = async (e: React.MouseEvent, projectId: number, projectName: string) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete workspace "${projectName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      setDeletingId(projectId);
      await deleteProject(projectId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete project.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-y-auto workspace-gradient-bg p-6 sm:p-8 md:p-10">
      <div className="max-w-7xl w-full mx-auto space-y-8">
        {/* Header Section */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-white/[0.08]">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-white">
                Project Workspaces
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-[#5146FF]/15 text-[#8B7CFF] border border-[#5146FF]/30">
                {projects.length} {projects.length === 1 ? "Workspace" : "Workspaces"}
              </span>
            </div>
            <p className="text-xs sm:text-sm text-[#A4A6B8] mt-1.5 leading-relaxed max-w-2xl">
              Organize multi-agent research environments, knowledge bases, and developer intelligence in isolated tenant workspaces.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <button
              type="button"
              onClick={() => {
                setError(null);
                refreshProjects();
              }}
              aria-label="Refresh workspaces"
              title="Refresh workspaces"
              className="px-3.5 py-2 rounded-xl text-xs font-medium text-[#A4A6B8] hover:text-white bg-[#20212B]/70 hover:bg-[#20212B] border border-white/[0.08] transition flex items-center gap-1.5 cursor-pointer"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
              <span>Refresh</span>
            </button>

            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-[#5146FF] hover:bg-[#4338e8] shadow-sm shadow-[#5146FF]/20 transition active:scale-95 flex items-center gap-2 cursor-pointer"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              <span>+ New Project</span>
            </button>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <ErrorState
            message={error}
            onRetry={() => {
              setError(null);
              refreshProjects();
            }}
          />
        )}

        {/* Content Area */}
        {loading && projects.length === 0 ? (
          <div className="py-16">
            <LoadingState message="Loading your project workspaces..." />
          </div>
        ) : projects.length === 0 ? (
          <div className="py-12">
            <div className="text-center p-12 border border-dashed border-white/[0.12] rounded-2xl bg-[#15151B]/60 max-w-lg mx-auto">
              <div className="w-12 h-12 rounded-xl bg-[#5146FF]/10 text-[#8B7CFF] flex items-center justify-center mx-auto mb-4 border border-[#5146FF]/20">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-white mb-2">No projects yet</h3>
              <p className="text-xs text-[#A4A6B8] mb-6 leading-relaxed">
                Create your first project workspace to start organizing research documents, multi-turn chat sessions, and developer operations.
              </p>
              <button
                type="button"
                onClick={() => setModalOpen(true)}
                className="px-5 py-2.5 rounded-xl text-xs font-semibold text-white bg-[#5146FF] hover:bg-[#4338e8] shadow-sm transition active:scale-95 inline-flex items-center gap-2 cursor-pointer"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                <span>Create Your First Project</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {projects.map((project) => {
              const isSelected = selectedProject?.id === project.id;
              const formattedDate = project.created_at
                ? new Date(project.created_at).toLocaleDateString(undefined, {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })
                : null;

              return (
                <div
                  key={project.id}
                  data-testid="project-card"
                  onClick={() => handleOpenWorkspace(project.id)}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      handleOpenWorkspace(project.id);
                    }
                  }}
                  className={`relative rounded-2xl bg-[#15151B] border transition-all duration-200 p-6 flex flex-col justify-between shadow-lg text-left group cursor-pointer select-none ${
                    isSelected
                      ? "border-[#5146FF] shadow-[#5146FF]/10 ring-1 ring-[#5146FF]/40"
                      : "border-white/[0.08] hover:border-white/[0.2] hover:bg-[#181820]"
                  }`}
                >
                  {/* Card Header & Metadata */}
                  <div>
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border ${
                            isSelected
                              ? "bg-[#5146FF]/20 text-[#8B7CFF] border-[#5146FF]/40"
                              : "bg-white/[0.04] text-[#A4A6B8] border-white/[0.08] group-hover:text-white"
                          }`}
                        >
                          <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                          </svg>
                        </div>
                        <h2 className="text-base font-semibold text-white truncate group-hover:text-[#8B7CFF] transition-colors">
                          {project.name}
                        </h2>
                      </div>

                      {isSelected ? (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shrink-0">
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                          Active
                        </span>
                      ) : (
                        <button
                          type="button"
                          onClick={(e) => handleDelete(e, project.id, project.name)}
                          disabled={deletingId === project.id}
                          aria-label={`Delete ${project.name}`}
                          title="Delete workspace"
                          className="opacity-0 group-hover:opacity-100 text-[#929292] hover:text-rose-400 p-1 rounded-lg hover:bg-white/[0.06] transition shrink-0"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 0 1-2.244 2.077H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
                          </svg>
                        </button>
                      )}
                    </div>

                    <p className="text-xs text-[#A4A6B8] line-clamp-3 leading-relaxed mb-6 min-h-[2.5rem]">
                      {project.description ? (
                        project.description
                      ) : (
                        <span className="text-[#929292] italic">No description provided.</span>
                      )}
                    </p>
                  </div>

                  {/* Card Footer */}
                  <div className="flex items-center justify-between pt-4 border-t border-white/[0.06] mt-auto">
                    <span className="text-[11px] text-[#929292]">
                      {formattedDate ? `Created ${formattedDate}` : `Workspace ID: #${project.id}`}
                    </span>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenWorkspace(project.id);
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition active:scale-95 flex items-center gap-1.5 ${
                        isSelected
                          ? "bg-white/[0.08] hover:bg-white/[0.12] text-white"
                          : "bg-[#5146FF] hover:bg-[#4338e8] text-white shadow-sm shadow-[#5146FF]/20"
                      }`}
                    >
                      <span>Open Workspace</span>
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <CreateProjectModal
        isOpen={modalOpen}
        onClose={() => {
          setModalOpen(false);
          refreshProjects();
        }}
      />
    </div>
  );
}
