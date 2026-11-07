"use client";

import React, { useEffect } from "react";
import { SessionItem } from "@/types/chat";

export interface SessionSidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
  sessions: SessionItem[];
  activeSessionId: number | null;
  onSelectSession: (sessionId: number) => void;
  onNewChat: () => void;
  loading?: boolean;
}

export function SessionSidebar({
  isOpen = false,
  onClose,
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  loading = false,
}: SessionSidebarProps) {
  useEffect(() => {
    if (!isOpen || !onClose) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Drawer Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 transition-opacity"
        onClick={onClose}
      />

      {/* Slide-over Recent Conversations Drawer */}
      <aside
        className="fixed inset-y-0 left-0 md:left-[250px] z-40 w-80 bg-[#15151B] border-r border-[#242424] flex flex-col h-full shadow-2xl transition-transform duration-200 ease-in-out select-none"
        aria-label="Recent Conversations"
      >
        {/* Drawer Header */}
        <div className="p-4 border-b border-[#242424] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-[#8B7CFF]" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <h2 className="text-sm font-semibold text-[#F8F8FC]">Recent Conversations</h2>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-[#929292] hover:text-[#F8F8FC] hover:bg-white/[0.06] transition"
              aria-label="Close recent conversations"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>

        {/* New Chat CTA Button */}
        <div className="p-3 border-b border-white/[0.06]">
          <button
            onClick={() => {
              onNewChat();
              if (onClose) onClose();
            }}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[#5146FF] hover:bg-[#4338e8] text-white text-xs font-semibold shadow-sm transition-colors cursor-pointer active:scale-98"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            <span>New Chat</span>
          </button>
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#929292]">
            Project History ({sessions.length})
          </div>

          {loading ? (
            <div className="p-4 text-center text-xs text-[#929292]">Loading sessions...</div>
          ) : sessions.length === 0 ? (
            <div className="p-4 text-center text-xs text-[#929292]">No previous conversations in this project</div>
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
                  onClick={() => {
                    onSelectSession(s.id);
                    if (onClose) onClose();
                  }}
                  className={`w-full text-left px-3 py-2.5 rounded-lg text-xs transition-colors cursor-pointer flex items-center justify-between ${
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
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                      />
                    </svg>
                    <span className="truncate">Session #{s.id}</span>
                  </div>
                  {dateStr && <span className="text-[10px] text-[#929292] flex-shrink-0 ml-2">{dateStr}</span>}
                </button>
              );
            })
          )}
        </div>
      </aside>
    </>
  );
}
