"use client";

import React, { useState } from "react";
import { useProject } from "@/features/projects/ProjectContext";

export function CreateProjectModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const { createProject } = useProject();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Project name is required.");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      await createProject(name.trim(), description.trim() || undefined);
      setName("");
      setDescription("");
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4">
      <div className="w-full max-w-md rounded-2xl bg-[#20212B] p-6 shadow-2xl border border-white/[0.12] text-[#F5F5F5]">
        <h2 className="text-xl font-bold text-[#F8F8FC] mb-2 tracking-tight">Create New Project</h2>
        <p className="text-xs text-[#A4A6B8] mb-4">
          Establish an isolated workspace for multi-agent research and development.
        </p>

        {error && (
          <div className="mb-4 rounded-lg bg-red-900/30 p-2.5 text-xs text-red-200 border border-red-500/30">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-[#A4A6B8] mb-1">Project Name *</label>
            <input
              type="text"
              required
              disabled={submitting}
              className="w-full bg-[#15151B] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#F5F5F5] placeholder-[#929292] focus:border-[#5146FF] focus:outline-none transition"
              placeholder="e.g. Distributed Core Refactor"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-[#A4A6B8] mb-1">Description</label>
            <textarea
              disabled={submitting}
              className="w-full bg-[#15151B] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#F5F5F5] placeholder-[#929292] focus:border-[#5146FF] focus:outline-none transition h-24 resize-none"
              placeholder="Brief summary of project scope and architecture..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="flex justify-end space-x-3 pt-2">
            <button
              type="button"
              disabled={submitting}
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-[#A4A6B8] hover:text-[#FFFFFF] hover:bg-white/[0.04] rounded-lg transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 text-xs font-medium bg-[#5146FF] hover:bg-[#4338e8] text-white rounded-lg shadow-sm transition active:scale-95 disabled:opacity-50"
            >
              {submitting ? "Creating..." : "Create Project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
