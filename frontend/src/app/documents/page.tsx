"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useProject } from "@/features/projects/ProjectContext";
import { api } from "@/services/apiClient";
import { DocumentResponse, DocumentDetailResponse } from "@/types/documents";
import { Card } from "@/components/ui/Card";
import { LoadingState, EmptyState } from "@/components/ui/StateWrappers";

export const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
export const ALLOWED_EXTENSIONS: readonly string[] = [".pdf", ".txt", ".md"];

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function DocumentsPage() {
  const { selectedProject, loading: projectLoading } = useProject();
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [pollTimedOut, setPollTimedOut] = useState<boolean>(false);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const pollingTicksRef = useRef<number>(0);

  const hasPending = documents.some(
    (d) => d.status === "uploaded" || d.status === "processing"
  );

  const pollingStatus = hasPending
    ? pollTimedOut
      ? "Documents are still processing. Click refresh to check status."
      : "Processing documents in background..."
    : null;

  useEffect(() => {
    if (!selectedProject) return;

    let active = true;
    const load = async () => {
      try {
        const data = await api.get<DocumentResponse[]>(`/projects/${selectedProject.id}/documents`);
        if (active) {
          setDocuments(data);
        }
      } catch {
        if (active) {
          setDocuments([]);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    load();

    return () => {
      active = false;
    };
  }, [selectedProject]);

  const fetchDocuments = useCallback(async () => {
    if (!selectedProject) return;

    try {
      setLoading(true);
      const data = await api.get<DocumentResponse[]>(`/projects/${selectedProject.id}/documents`);
      setDocuments(data);
      setPollTimedOut(false);
      pollingTicksRef.current = 0;
    } catch {
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  }, [selectedProject]);

  // Bounded polling controller: poll every 3s while documents are in 'uploaded' or 'processing' state
  useEffect(() => {
    if (!selectedProject || !hasPending) {
      pollingTicksRef.current = 0;
      return;
    }

    const interval = setInterval(async () => {
      if (pollingTicksRef.current >= 10) {
        setPollTimedOut(true);
        clearInterval(interval);
        return;
      }
      pollingTicksRef.current += 1;
      try {
        const data = await api.get<DocumentResponse[]>(
          `/projects/${selectedProject.id}/documents`
        );
        setDocuments(data);
      } catch {
        // Polling failure, halt gracefully
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [hasPending, selectedProject]);

  const processFile = async (file: File) => {
    if (!selectedProject) return;
    setUploadError("");

    // 1. Client-side extension validation
    const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadError(
        `Unsupported file type '${ext}'. Allowed types: ${ALLOWED_EXTENSIONS.join(", ")}`
      );
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    // 2. Client-side size validation (10MB)
    if (file.size > MAX_FILE_SIZE) {
      setUploadError(
        `File size (${formatBytes(file.size)}) exceeds maximum limit of 10MB.`
      );
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    if (file.size === 0) {
      setUploadError("Uploaded file cannot be empty.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const created = await api.post<DocumentDetailResponse>(
        `/projects/${selectedProject.id}/documents`,
        formData
      );

      setDocuments((prev) => [created, ...prev]);
      pollingTicksRef.current = 0;
      setPollTimedOut(false);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Failed to upload document");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await processFile(file);
    }
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      await processFile(file);
    }
  };

  const handleDelete = async (docId: number) => {
    if (!selectedProject) return;
    if (!window.confirm("Are you sure you want to delete this document from the knowledge base?")) {
      return;
    }

    try {
      await api.delete(`/projects/${selectedProject.id}/documents/${docId}`);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Failed to delete document");
    }
  };

  if (projectLoading || loading) {
    return (
      <div className="p-8 workspace-gradient-bg min-h-[calc(100vh-3.5rem)]">
        <LoadingState message="Loading project documents..." />
      </div>
    );
  }

  if (!selectedProject) {
    return (
      <div className="p-8 workspace-gradient-bg min-h-[calc(100vh-3.5rem)]">
        <div className="max-w-xl mx-auto mt-12">
          <EmptyState
            title="No Project Selected"
            description="Please select or create a project workspace from the header before managing knowledge base documents."
          />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 sm:p-8 space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#F8F8FC] tracking-tight">
            Knowledge Ingestion
          </h1>
          <p className="text-xs sm:text-sm text-[#A4A6B8] mt-1 max-w-2xl">
            Documents uploaded here are chunked, embedded, and stored in Qdrant for hybrid RAG and
            citation verification.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              pollingTicksRef.current = 0;
              fetchDocuments();
            }}
            className="rounded-lg border border-white/[0.08] bg-[#20212B] px-3 py-1.5 text-xs font-semibold text-[#A4A6B8] hover:text-[#F8F8FC] hover:bg-[#262836] shadow-sm transition cursor-pointer"
          >
            Refresh
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-1.5 rounded-lg bg-[#5146FF] hover:bg-[#4338e8] px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition active:scale-95 disabled:opacity-50 cursor-pointer"
          >
            {uploading ? (
              <>
                <svg className="animate-spin h-3.5 w-3.5 text-white" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                <span>Upload Document</span>
              </>
            )}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.txt,.md"
            onChange={handleFileUpload}
          />
        </div>
      </div>

      {/* Drag & Drop Upload Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`p-6 rounded-2xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center text-center ${
          isDragging
            ? "border-[#5146FF] bg-[#5146FF]/10 scale-[1.01]"
            : "border-white/[0.12] bg-[#20212B]/50 hover:bg-[#20212B] hover:border-white/20"
        }`}
      >
        <div className="w-10 h-10 rounded-xl bg-[#5146FF]/15 text-[#8B7CFF] flex items-center justify-center mb-2.5">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
        </div>
        <p className="text-sm font-medium text-[#F8F8FC]">
          Drag and drop your document here, or browse
        </p>
        <p className="text-xs text-[#929292] mt-1">
          PDF, Plain Text, or Markdown (up to 10MB)
        </p>
      </div>

      {uploadError && (
        <div className="rounded-xl bg-rose-500/10 p-4 text-xs text-rose-300 border border-rose-500/20">
          <strong className="font-semibold text-rose-200">Upload Error:</strong> {uploadError}
        </div>
      )}

      {pollingStatus && (
        <div className="flex items-center justify-between rounded-xl bg-[#5146FF]/15 p-3 text-xs text-[#8B7CFF] border border-[#5146FF]/30">
          <span className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-[#5146FF] animate-pulse" />
            <span>{pollingStatus}</span>
          </span>
          <button
            onClick={() => {
              pollingTicksRef.current = 0;
              fetchDocuments();
            }}
            className="font-semibold underline hover:text-white cursor-pointer"
          >
            Check Now
          </button>
        </div>
      )}

      {documents.length === 0 ? (
        <Card className="text-center p-12">
          <p className="text-[#A4A6B8] mb-2 font-medium">No documents have been ingested for this project yet.</p>
          <p className="text-xs text-[#929292] mb-6">
            Supported formats: PDF (.pdf), Plain Text (.txt), Markdown (.md) up to 10MB.
          </p>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#20212B] hover:bg-[#262836] border border-white/[0.1] text-xs font-semibold text-[#F8F8FC] transition shadow-sm cursor-pointer"
          >
            Select Document to Ingest
          </button>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0 border border-white/[0.08]">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-white/[0.06] text-xs">
              <thead className="bg-[#15151B] text-[#929292]">
                <tr>
                  <th className="px-6 py-3.5 text-left font-semibold uppercase tracking-wider text-[11px]">Filename</th>
                  <th className="px-6 py-3.5 text-left font-semibold uppercase tracking-wider text-[11px]">Size</th>
                  <th className="px-6 py-3.5 text-left font-semibold uppercase tracking-wider text-[11px]">Status</th>
                  <th className="px-6 py-3.5 text-left font-semibold uppercase tracking-wider text-[11px]">Chunks</th>
                  <th className="px-6 py-3.5 text-left font-semibold uppercase tracking-wider text-[11px]">Uploaded</th>
                  <th className="px-6 py-3.5 text-right font-semibold uppercase tracking-wider text-[11px]">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04] bg-[#20212B]">
                {documents.map((doc) => {
                  let badge = (
                    <span className="rounded-md bg-white/[0.06] px-2 py-0.5 text-[11px] font-medium text-[#A4A6B8]">
                      {doc.status}
                    </span>
                  );

                  if (doc.status === "indexed") {
                    badge = (
                      <span className="inline-flex items-center gap-1 rounded-md bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[11px] font-medium text-emerald-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        Indexed
                      </span>
                    );
                  } else if (doc.status === "uploaded" || doc.status === "processing") {
                    badge = (
                      <span className="inline-flex items-center gap-1.5 rounded-md bg-[#5146FF]/15 border border-[#5146FF]/30 px-2 py-0.5 text-[11px] font-medium text-[#8B7CFF]">
                        <span className="h-1.5 w-1.5 rounded-full bg-[#5146FF] animate-pulse" />
                        <span>{doc.status === "uploaded" ? "Uploaded" : "Processing"}</span>
                      </span>
                    );
                  } else if (doc.status === "failed") {
                    badge = (
                      <span className="inline-flex items-center gap-1 rounded-md bg-rose-500/15 border border-rose-500/30 px-2 py-0.5 text-[11px] font-medium text-rose-400">
                        Failed
                      </span>
                    );
                  }

                  return (
                    <tr key={doc.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="px-6 py-4 font-mono font-medium text-[#F8F8FC]">
                        {doc.original_filename}
                      </td>
                      <td className="px-6 py-4 text-[#A4A6B8]">{formatBytes(doc.size_bytes)}</td>
                      <td className="px-6 py-4">{badge}</td>
                      <td className="px-6 py-4 text-[#A4A6B8] font-mono">{doc.chunk_count}</td>
                      <td className="px-6 py-4 text-[#929292] text-xs">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleDelete(doc.id)}
                          className="text-xs font-medium text-rose-400 hover:text-rose-300 transition cursor-pointer"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
