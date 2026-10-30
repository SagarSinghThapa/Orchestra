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
      <div className="relative flex items-center space-x-3">
        <button
          type="button"
          onClick={() => setDropdownOpen((prev) => !prev)}
          className="flex items-center space-x-2 rounded border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <span className="max-w-[200px] truncate">
            {loading
              ? "Loading projects..."
              : selectedProject
              ? selectedProject.name
              : "Select a Project"}
          </span>
          <svg
            className="h-4 w-4 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded-full border border-green-200">
          Connected
        </span>

        {/* Dropdown Menu */}
        {dropdownOpen && (
          <div className="absolute top-full left-0 mt-1 w-64 rounded-md border border-gray-200 bg-white shadow-lg z-50">
            <div className="p-2 border-b">
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                Your Workspaces
              </p>
            </div>
            <div className="max-h-60 overflow-auto py-1">
              {projects.length === 0 ? (
                <p className="p-3 text-xs text-gray-500 text-center">No projects created yet.</p>
              ) : (
                projects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => {
                      selectProject(project.id);
                      setDropdownOpen(false);
                    }}
                    className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-blue-50 ${
                      selectedProject?.id === project.id
                        ? "bg-blue-50 font-semibold text-blue-700"
                        : "text-gray-700"
                    }`}
                  >
                    <span className="truncate">{project.name}</span>
                    {selectedProject?.id === project.id && (
                      <span className="text-blue-600 text-xs font-bold">✓</span>
                    )}
                  </button>
                ))
              )}
            </div>
            <div className="border-t p-2">
              <button
                onClick={() => {
                  setDropdownOpen(false);
                  setModalOpen(true);
                }}
                className="w-full text-center rounded bg-gray-50 py-1.5 text-xs font-medium text-blue-600 hover:bg-blue-100"
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
