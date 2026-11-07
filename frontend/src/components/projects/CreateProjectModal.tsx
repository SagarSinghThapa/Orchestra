"use client";

import React, { useState, useEffect, useRef, useCallback, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import { useProject } from "@/features/projects/ProjectContext";

const emptySubscribe = () => () => {};

export function CreateProjectModal({
  isOpen,
  onClose,
}: {
  isOpen: boolean;
  onClose: () => void;
}) {
  const { createProject } = useProject();
  const mounted = useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false
  );
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const modalRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);

  const handleClose = useCallback(() => {
    setName("");
    setDescription("");
    setError("");
    onClose();
  }, [onClose]);

  // Save previous active element when opened and restore on unmount/close
  useEffect(() => {
    if (isOpen) {
      if (typeof document !== "undefined") {
        previousActiveElementRef.current = document.activeElement as HTMLElement;
      }

      // Focus first input after slight delay for portal mount
      const timer = setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
      return () => clearTimeout(timer);
    } else if (previousActiveElementRef.current) {
      previousActiveElementRef.current.focus?.();
    }
  }, [isOpen]);

  // Focus trap and Escape key listener
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (!submitting) {
          e.preventDefault();
          handleClose();
        }
        return;
      }

      if (e.key === "Tab" && modalRef.current) {
        const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, submitting, handleClose]);

  if (!isOpen || !mounted) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("Project name is required.");
      inputRef.current?.focus();
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      await createProject(trimmedName, description.trim() || undefined);
      handleClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create project");
    } finally {
      setSubmitting(false);
    }
  };

  const modalContent = (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-project-title"
      aria-describedby="create-project-desc"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 sm:p-6 overflow-y-auto"
      onMouseDown={(e) => {
        if (!submitting && e.target === e.currentTarget) {
          handleClose();
        }
      }}
    >
      <div
        ref={modalRef}
        className="relative w-full max-w-md my-auto rounded-2xl bg-[#20212B] p-6 shadow-2xl border border-white/[0.12] text-[#F5F5F5] max-h-[90vh] flex flex-col"
      >
        {/* Close button */}
        <button
          type="button"
          onClick={() => {
            if (!submitting) handleClose();
          }}
          disabled={submitting}
          className="absolute top-4 right-4 text-[#929292] hover:text-[#F8F8FC] p-1.5 rounded-lg hover:bg-white/[0.06] transition disabled:opacity-50 cursor-pointer"
          aria-label="Close modal"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <h2 id="create-project-title" className="text-xl font-bold text-[#F8F8FC] mb-1.5 tracking-tight">
          Create New Project
        </h2>
        <p id="create-project-desc" className="text-xs text-[#A4A6B8] mb-4">
          Establish an isolated workspace for multi-agent research and development.
        </p>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded-lg bg-red-900/30 p-2.5 text-xs text-red-200 border border-red-500/30"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 overflow-y-auto pr-1">
          <div>
            <label htmlFor="project-name-input" className="block text-xs font-medium text-[#A4A6B8] mb-1">
              Project Name <span className="text-red-400">*</span>
            </label>
            <input
              id="project-name-input"
              ref={inputRef}
              type="text"
              required
              disabled={submitting}
              className="w-full bg-[#15151B] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#F5F5F5] placeholder-[#929292] focus:border-[#5146FF] focus:outline-none transition disabled:opacity-50"
              placeholder="e.g. Distributed Core Refactor"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (error) setError("");
              }}
            />
          </div>

          <div>
            <label htmlFor="project-desc-input" className="block text-xs font-medium text-[#A4A6B8] mb-1">
              Description <span className="text-[#929292] text-[11px]">(optional)</span>
            </label>
            <textarea
              id="project-desc-input"
              disabled={submitting}
              className="w-full bg-[#15151B] border border-white/[0.08] rounded-lg px-3 py-2 text-sm text-[#F5F5F5] placeholder-[#929292] focus:border-[#5146FF] focus:outline-none transition h-24 resize-none disabled:opacity-50"
              placeholder="Brief summary of project scope and architecture..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="flex justify-end space-x-3 pt-2">
            <button
              type="button"
              disabled={submitting}
              onClick={handleClose}
              className="px-4 py-2 text-xs font-medium text-[#A4A6B8] hover:text-[#FFFFFF] hover:bg-white/[0.04] rounded-lg transition disabled:opacity-50 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium bg-[#5146FF] hover:bg-[#4338e8] text-white rounded-lg shadow-sm transition active:scale-95 disabled:opacity-50 cursor-pointer"
            >
              {submitting ? (
                <>
                  <svg className="animate-spin h-3.5 w-3.5 text-white" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>Creating...</span>
                </>
              ) : (
                "Create Project"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? createPortal(modalContent, document.body) : null;
}

