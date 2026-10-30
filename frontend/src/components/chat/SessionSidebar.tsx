"use client";

import React from "react";
import { SessionItem } from "@/types/chat";

interface SessionSidebarProps {
  sessions: SessionItem[];
  activeSessionId: number | null;
  onSelectSession: (sessionId: number) => void;
  onNewChat: () => void;
  loading?: boolean;
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  loading = false,
}: SessionSidebarProps) {
  return (
    <aside className="w-64 border-r border-gray-200 bg-gray-50 flex flex-col h-full flex-shrink-0">
      {/* New Chat Action */}
      <div className="p-3 border-b border-gray-200">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 text-xs font-semibold shadow-sm transition-colors cursor-pointer"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>New Chat</span>
        </button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-gray-400">
          History ({sessions.length})
        </div>

        {loading ? (
          <div className="p-4 text-center text-xs text-gray-400">Loading sessions...</div>
        ) : sessions.length === 0 ? (
          <div className="p-4 text-center text-xs text-gray-400">No previous sessions</div>
        ) : (
          sessions.map((s) => {
            const isActive = activeSessionId === s.id;
            const dateStr = s.created_at
              ? new Date(s.created_at).toLocaleDateString([], {
                  month: "short",
                  day: "numeric",
                })
              : "";

            return (
              <button
                key={s.id}
                onClick={() => onSelectSession(s.id)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors cursor-pointer flex items-center justify-between ${
                  isActive
                    ? "bg-white text-blue-700 font-semibold shadow-sm border border-gray-200"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <svg
                    className={`h-3.5 w-3.5 flex-shrink-0 ${isActive ? "text-blue-600" : "text-gray-400"}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                    />
                  </svg>
                  <span className="truncate">Session #{s.id}</span>
                </div>
                {dateStr && <span className="text-[10px] text-gray-400 flex-shrink-0">{dateStr}</span>}
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
