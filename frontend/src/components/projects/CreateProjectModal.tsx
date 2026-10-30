"use client";

import React, { useState } from "react";
import { useProject } from "@/features/projects/ProjectContext";
import { Button } from "@/components/ui/Button";

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl border">
        <h2 className="text-xl font-bold text-gray-900 mb-2">Create New Project</h2>
        <p className="text-sm text-gray-500 mb-4">
          Establish an isolated workspace for multi-agent research and development.
        </p>

        {error && (
          <div className="mb-4 rounded bg-red-50 p-2 text-sm text-red-700 border border-red-200">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Project Name *</label>
            <input
              type="text"
              required
              disabled={submitting}
              className="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="e.g. Distributed Core Refactor"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Description</label>
            <textarea
              disabled={submitting}
              className="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 h-24"
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
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded"
            >
              Cancel
            </button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Creating..." : "Create Project"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
