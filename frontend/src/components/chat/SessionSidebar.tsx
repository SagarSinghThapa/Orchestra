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
    <aside className="w-64 border-r border-white/[0.08] bg-[#15151B] flex flex-col h-full flex-shrink-0">
      {/* New Chat Action */}
      <div className="p-3 border-b border-white/[0.06]">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[#5146FF] hover:bg-[#4338e8] text-white text-xs font-semibold shadow-sm transition-colors cursor-pointer active:scale-98"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          <span>New Chat</span>
        </button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#929292]">
          Conversations ({sessions.length})
        </div>

        {loading ? (
          <div className="p-4 text-center text-xs text-[#929292]">Loading sessions...</div>
        ) : sessions.length === 0 ? (
          <div className="p-4 text-center text-xs text-[#929292]">No previous sessions</div>
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
                    ? "bg-[#20212B] text-white font-medium border border-white/[0.08]"
                    : "text-[#A4A6B8] hover:bg-white/[0.04] hover:text-[#F8F8FC]"
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <div
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      isActive ? "bg-[#5146FF]" : "bg-transparent"
                    }`}
                  />
                  <svg
                    className={`h-3.5 w-3.5 flex-shrink-0 ${isActive ? "text-[#8B7CFF]" : "text-[#929292]"}`}
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
                {dateStr && <span className="text-[10px] text-[#929292] flex-shrink-0">{dateStr}</span>}
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
