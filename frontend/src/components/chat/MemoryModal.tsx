"use client";

import React, { useEffect, useState } from "react";
import { MemoryStats } from "@/types/chat";
import { api } from "@/services/apiClient";

interface MemoryModalProps {
  projectId: number;
  sessionId: number;
  isOpen: boolean;
  onClose: () => void;
}

export function MemoryModal({ projectId, sessionId, isOpen, onClose }: MemoryModalProps) {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [confirmReset, setConfirmReset] = useState<boolean>(false);

  useEffect(() => {
    let active = true;

    const fetchStats = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.get<MemoryStats>(
          `/projects/${projectId}/sessions/${sessionId}/memory/stats`
        );
        if (active) {
          setStats(data);
        }
      } catch (err: unknown) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load memory stats");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    fetchStats();

    return () => {
      active = false;
    };
  }, [projectId, sessionId]);

  if (!isOpen) return null;

  const handleReset = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await api.delete(`/projects/${projectId}/sessions/${sessionId}/memory`);
      setConfirmReset(false);
      // Reload stats after deletion
      const fresh = await api.get<MemoryStats>(
        `/projects/${projectId}/sessions/${sessionId}/memory/stats`
      );
      setStats(fresh);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to reset session memory");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRebuild = async () => {
    setActionLoading(true);
    setError(null);
    try {
      await api.post(`/projects/${projectId}/sessions/${sessionId}/memory/rebuild`);
      // Reload stats after rebuild
      const fresh = await api.get<MemoryStats>(
        `/projects/${projectId}/sessions/${sessionId}/memory/stats`
      );
      setStats(fresh);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to trigger memory rebuild");
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50">
          <div className="flex items-center gap-2">
            <svg className="h-5 w-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"
              />
            </svg>
            <h3 className="font-semibold text-gray-900 text-sm">
              Session Memory &amp; Telemetry
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-sm font-bold p-1 cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {error && (
            <div className="mb-4 rounded-md bg-red-50 p-3 border border-red-200 text-xs text-red-700">
              {error}
            </div>
          )}

          {loading ? (
            <div className="py-8 text-center text-xs text-gray-500 flex flex-col items-center gap-2">
              <svg className="animate-spin h-5 w-5 text-blue-600" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>Loading telemetry stats...</span>
            </div>
          ) : stats ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div className="text-[11px] text-gray-500 font-medium">Derived Summary</div>
                  <div className="text-base font-bold text-gray-900 mt-1 flex items-center gap-1.5">
                    {stats.summary_exists ? (
                      <>
                        <span className="h-2 w-2 rounded-full bg-emerald-500" />
                        <span>Active (v{stats.summary_version})</span>
                      </>
                    ) : (
                      <>
                        <span className="h-2 w-2 rounded-full bg-gray-400" />
                        <span className="text-gray-500">None</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div className="text-[11px] text-gray-500 font-medium">Assembled Context</div>
                  <div className="text-base font-bold text-gray-900 mt-1">
                    {stats.assembled_context_chars.toLocaleString()}{" "}
                    <span className="text-xs font-normal text-gray-500">chars</span>
                  </div>
                </div>

                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div className="text-[11px] text-gray-500 font-medium">Summarized Messages</div>
                  <div className="text-base font-bold text-gray-900 mt-1">
                    {stats.messages_summarized_count}
                  </div>
                </div>

                <div className="p-3 bg-gray-50 rounded-lg border border-gray-100">
                  <div className="text-[11px] text-gray-500 font-medium">Active Sliding Window</div>
                  <div className="text-base font-bold text-gray-900 mt-1">
                    {stats.sliding_window_message_count}{" "}
                    <span className="text-xs font-normal text-gray-500">recent msgs</span>
                  </div>
                </div>
              </div>

              <div className="text-[11px] text-gray-400 font-mono px-1">
                Watermark Message ID: {stats.message_watermark_id || 0}
              </div>

              {/* Action Controls */}
              <div className="pt-4 border-t border-gray-100 space-y-3">
                {confirmReset ? (
                  <div className="bg-red-50 p-3.5 rounded-lg border border-red-200">
                    <p className="text-xs text-red-800 font-medium mb-2">
                      Reset memory for this session? This deletes the derived context summary row.
                      Your actual chat messages will NOT be deleted.
                    </p>
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => setConfirmReset(false)}
                        disabled={actionLoading}
                        className="px-3 py-1.5 text-xs text-gray-600 hover:text-gray-800 font-medium cursor-pointer"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleReset}
                        disabled={actionLoading}
                        className="px-3 py-1.5 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-md shadow-sm disabled:opacity-50 cursor-pointer"
                      >
                        {actionLoading ? "Resetting..." : "Confirm Reset"}
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between gap-3">
                    <button
                      onClick={() => setConfirmReset(true)}
                      disabled={actionLoading || !stats.summary_exists}
                      className="px-3 py-1.5 rounded-md text-xs font-medium text-red-600 border border-red-200 hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                    >
                      Reset Memory
                    </button>
                    <button
                      onClick={handleRebuild}
                      disabled={actionLoading}
                      className="px-3 py-1.5 rounded-md text-xs font-medium text-blue-600 border border-blue-200 hover:bg-blue-50 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer flex items-center gap-1.5"
                    >
                      {actionLoading && (
                        <svg className="animate-spin h-3 w-3 text-blue-600" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                        </svg>
                      )}
                      <span>Rebuild Memory</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
