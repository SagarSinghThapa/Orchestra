"use client";

import React, { useState } from "react";
import { useProject } from "@/features/projects/ProjectContext";
import { CreateProjectModal } from "./CreateProjectModal";

export function ProjectSelector() {
  const { projects, selectedProject, selectProject, loading } = useProject();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <div className="relative flex items-center gap-2 sm:gap-3">
        <button
          type="button"
          onClick={() => setDropdownOpen((prev) => !prev)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#20212B]/70 hover:bg-[#20212B] border border-white/[0.08] text-xs font-medium text-[#F5F5F5] transition focus:outline-none focus:ring-1 focus:ring-[#5146FF]"
        >
          <div className="w-2 h-2 rounded-sm bg-[#5146FF] shrink-0" />
          <span className="truncate max-w-[150px] sm:max-w-[220px]">
            {loading
              ? "Loading projects..."
              : selectedProject
              ? selectedProject.name
              : "Select a Project"}
          </span>
          <svg
            className="w-3.5 h-3.5 text-[#929292] shrink-0"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
          </svg>
        </button>

        {/* Dropdown Menu */}
        {dropdownOpen && (
          <div className="absolute top-full left-0 mt-2 w-64 rounded-xl border border-white/[0.08] bg-[#20212B] shadow-2xl z-50 p-1.5 backdrop-blur-md">
            <div className="px-2.5 py-1.5 border-b border-white/[0.06]">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[#929292]">
                Your Workspaces
              </p>
            </div>
            <div className="max-h-60 overflow-auto py-1">
              {projects.length === 0 ? (
                <p className="p-3 text-xs text-[#929292] text-center">No projects created yet.</p>
              ) : (
                projects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => {
                      selectProject(project.id);
                      setDropdownOpen(false);
                    }}
                    className={`flex w-full items-center justify-between px-2.5 py-2 rounded-lg text-left text-xs transition ${
                      selectedProject?.id === project.id
                        ? "bg-[#5146FF]/15 text-[#FFFFFF] font-medium"
                        : "text-[#A4A6B8] hover:bg-white/[0.04] hover:text-[#FFFFFF]"
                    }`}
                  >
                    <span className="truncate">{project.name}</span>
                    {selectedProject?.id === project.id && (
                      <span className="text-[#5146FF] text-xs font-bold">✓</span>
                    )}
                  </button>
                ))
              )}
            </div>
            <div className="border-t border-white/[0.06] pt-1.5">
              <button
                onClick={() => {
                  setDropdownOpen(false);
                  setModalOpen(true);
                }}
                className="w-full text-center rounded-lg bg-[#5146FF]/10 py-1.5 text-xs font-medium text-[#8B7CFF] hover:bg-[#5146FF]/20 transition border border-[#5146FF]/20"
              >
                + Create New Project
              </button>
            </div>
          </div>
        )}
      </div>

      <CreateProjectModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  );
}
