"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useProject } from "@/features/projects/ProjectContext";
import { api } from "@/services/apiClient";
import { DocumentResponse, DocumentDetailResponse } from "@/types/documents";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedProject) return;

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
      pollingTicksRef.current = 0; // Reset polling ticks for new upload
      setPollTimedOut(false);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Failed to upload document");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
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
    return <LoadingState message="Loading project documents..." />;
  }

  if (!selectedProject) {
    return (
      <div className="max-w-xl mx-auto mt-12">
        <EmptyState
          title="No Project Selected"
          description="Please select or create a project workspace from the header before managing knowledge base documents."
        />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Knowledge Ingestion</h1>
          <p className="text-sm text-gray-500 mt-1">
            Documents uploaded here are chunked, embedded, and stored in Qdrant for hybrid RAG and
            citation verification.
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => {
              pollingTicksRef.current = 0;
              fetchDocuments();
            }}
            className="rounded border border-gray-300 bg-white px-3 py-1.5 text-xs font-semibold text-gray-700 shadow-sm hover:bg-gray-50"
          >
            Refresh
          </button>
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? "Uploading..." : "Upload Document"}
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            accept=".pdf,.txt,.md"
            onChange={handleFileUpload}
          />
        </div>
      </div>

      {uploadError && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700 border border-red-200">
          <strong>Upload Error:</strong> {uploadError}
        </div>
      )}

      {pollingStatus && (
        <div className="flex items-center justify-between rounded-md bg-blue-50 p-3 text-xs text-blue-700 border border-blue-200">
          <span className="flex items-center space-x-2">
            <span className="h-2 w-2 rounded-full bg-blue-600 animate-pulse" />
            <span>{pollingStatus}</span>
          </span>
          <button
            onClick={() => {
              pollingTicksRef.current = 0;
              fetchDocuments();
            }}
            className="font-medium underline hover:text-blue-900"
          >
            Check Now
          </button>
        </div>
      )}

      {documents.length === 0 ? (
        <Card className="text-center p-12">
          <p className="text-gray-500 mb-4">No documents have been ingested for this project yet.</p>
          <p className="text-xs text-gray-400 mb-6">
            Supported formats: PDF (.pdf), Plain Text (.txt), Markdown (.md) up to 10MB.
          </p>
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            variant="secondary"
          >
            Select Document to Ingest
          </Button>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0 border">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-6 py-3 text-left font-semibold">Filename</th>
                <th className="px-6 py-3 text-left font-semibold">Size</th>
                <th className="px-6 py-3 text-left font-semibold">Status</th>
                <th className="px-6 py-3 text-left font-semibold">Chunks</th>
                <th className="px-6 py-3 text-left font-semibold">Uploaded</th>
                <th className="px-6 py-3 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {documents.map((doc) => {
                let badge = (
                  <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-700">
                    {doc.status}
                  </span>
                );

                if (doc.status === "indexed") {
                  badge = (
                    <span className="rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                      Indexed
                    </span>
                  );
                } else if (doc.status === "uploaded" || doc.status === "processing") {
                  badge = (
                    <span className="flex items-center space-x-1 rounded bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                      <span className="h-1.5 w-1.5 rounded-full bg-blue-600 animate-pulse" />
                      <span>{doc.status === "uploaded" ? "Uploaded" : "Processing"}</span>
                    </span>
                  );
                } else if (doc.status === "failed") {
                  badge = (
                    <span className="rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">
                      Failed
                    </span>
                  );
                }

                return (
                  <tr key={doc.id} className="hover:bg-gray-50/50">
                    <td className="px-6 py-4 font-mono font-medium text-gray-900">
                      {doc.original_filename}
                    </td>
                    <td className="px-6 py-4 text-gray-500">{formatBytes(doc.size_bytes)}</td>
                    <td className="px-6 py-4">{badge}</td>
                    <td className="px-6 py-4 text-gray-500 font-mono">{doc.chunk_count}</td>
                    <td className="px-6 py-4 text-gray-400 text-xs">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="text-xs font-medium text-red-600 hover:text-red-900"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
