"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useProject } from "@/features/projects/ProjectContext";
import { SessionSidebar } from "@/components/chat/SessionSidebar";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { MessageInput } from "@/components/chat/MessageInput";
import { MemoryModal } from "@/components/chat/MemoryModal";
import { Message, OrchestratorRequest, OrchestratorResponse, SessionItem } from "@/types/chat";
import { api } from "@/services/apiClient";
import { EmptyState } from "@/components/ui/StateWrappers";

export default function ChatPage() {
  const { selectedProject } = useProject();
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingSessions, setLoadingSessions] = useState<boolean>(false);
  const [loadingMessages, setLoadingMessages] = useState<boolean>(false);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [memoryModalOpen, setMemoryModalOpen] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isExecuting]);

  // Load sessions when project changes
  useEffect(() => {
    if (!selectedProject) {
      return;
    }

    let active = true;
    const fetchSessions = async () => {
      setLoadingSessions(true);
      try {
        const data = await api.get<SessionItem[]>(`/sessions/project/${selectedProject.id}`);
        if (active) {
          setSessions(data);
        }
      } catch {
        if (active) {
          setSessions([]);
        }
      } finally {
        if (active) {
          setLoadingSessions(false);
        }
      }
    };

    fetchSessions();

    return () => {
      active = false;
    };
  }, [selectedProject]);

  // Load message history when active session changes
  useEffect(() => {
    if (!activeSessionId) {
      return;
    }

    let active = true;
    const fetchHistory = async () => {
      setLoadingMessages(true);
      setErrorBanner(null);
      try {
        const raw = await api.get<Message[]>(`/sessions/${activeSessionId}/messages`);
        if (active) {
          setMessages(
            raw.map((m) => ({
              ...m,
              state: "confirmed",
            }))
          );
        }
      } catch (err: unknown) {
        if (active) {
          setErrorBanner(err instanceof Error ? err.message : "Failed to load session history");
          setMessages([]);
        }
      } finally {
        if (active) {
          setLoadingMessages(false);
        }
      }
    };

    fetchHistory();

    return () => {
      active = false;
    };
  }, [activeSessionId]);

  const handleSelectSession = (id: number) => {
    setActiveSessionId(id);
  };

  const handleNewChat = () => {
    setActiveSessionId(null);
    setMessages([]);
    setErrorBanner(null);
  };

  const handleSendMessage = useCallback(async (content: string) => {
    if (!selectedProject || isExecuting) return;

    setErrorBanner(null);

    // Optimistically push user message
    const tempUserMsg: Message = {
      role: "user",
      content,
      created_at: new Date().toISOString(),
      state: "sending",
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setIsExecuting(true);

    try {
      const payload: OrchestratorRequest = {
        prompt: content,
        session_id: activeSessionId,
      };

      const response = await api.post<OrchestratorResponse>(
        `/projects/${selectedProject.id}/orchestrate`,
        payload
      );

      // Mark user message confirmed
      setMessages((prev) =>
        prev.map((m, idx) => (idx === prev.length - 1 ? { ...m, state: "confirmed" } : m))
      );

      // If new session created, adopt ID and add to session list
      if (!activeSessionId || activeSessionId !== response.session_id) {
        setActiveSessionId(response.session_id);
        const newSessionItem: SessionItem = {
          id: response.session_id,
          project_id: selectedProject.id,
          type: "orchestrator",
          status: "active",
          created_at: new Date().toISOString(),
        };
        setSessions((prev) => [newSessionItem, ...prev.filter((s) => s.id !== response.session_id)]);
      }

      // Append assistant message
      const assistantMsg: Message = {
        role: "assistant",
        content: response.answer,
        created_at: new Date().toISOString(),
        intent: response.intent,
        research_result: response.research_result,
        developer_result: response.developer_result,
        execution_trace: response.execution_trace,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: unknown) {
      // Mark user message as failed
      setMessages((prev) =>
        prev.map((m, idx) => (idx === prev.length - 1 ? { ...m, state: "failed" } : m))
      );
      setErrorBanner(
        err instanceof Error ? err.message : "Failed to receive response from orchestrator."
      );
    } finally {
      setIsExecuting(false);
    }
  }, [selectedProject, isExecuting, activeSessionId]);

  const handleRetryLast = useCallback(async () => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMsg) {
      // Remove failed message and re-send
      setMessages((prev) => prev.slice(0, prev.length - 1));
      await handleSendMessage(lastUserMsg.content);
    }
  }, [messages, handleSendMessage]);

  if (!selectedProject) {
    return (
      <div className="max-w-4xl mx-auto py-12 px-4">
        <EmptyState
          title="No Project Selected"
          description="Please select or create an active project workspace from the top navigation to begin an Orchestrator chat."
        />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] overflow-hidden bg-white">
      {/* Session Navigation Sidebar */}
      <SessionSidebar
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        loading={loadingSessions}
      />

      {/* Main Chat Pane */}
      <div className="flex-1 flex flex-col h-full overflow-hidden">
        {/* Chat Header */}
        <div className="px-6 py-3 border-b border-gray-200 bg-white flex items-center justify-between flex-shrink-0">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-gray-900">
                {activeSessionId ? `Session #${activeSessionId}` : "New Conversation"}
              </h2>
              <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-gray-100 text-gray-700">
                Workspace: {selectedProject.name}
              </span>
            </div>
            <p className="text-[11px] text-gray-500 mt-0.5">
              Connected to Main LangGraph Orchestrator (Direct Q&amp;A, Research, Developer Intelligence)
            </p>
          </div>

          <div className="flex items-center gap-2">
            {activeSessionId && (
              <button
                onClick={() => setMemoryModalOpen(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 text-xs font-semibold text-gray-700 shadow-sm transition-colors cursor-pointer"
              >
                <svg className="h-4 w-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"
                  />
                </svg>
                <span>Memory Telemetry</span>
              </button>
            )}
          </div>
        </div>

        {/* Error Banner */}
        {errorBanner && (
          <div className="px-6 py-2 bg-red-50 border-b border-red-200 text-xs text-red-700 flex items-center justify-between">
            <span>{errorBanner}</span>
            <button
              onClick={() => setErrorBanner(null)}
              className="text-red-500 hover:text-red-700 font-bold ml-4 cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}

        {/* Messages Scroll Area */}
        <div className="flex-1 overflow-y-auto px-6 py-6 bg-gray-50/50">
          {loadingMessages ? (
            <div className="h-full flex items-center justify-center text-xs text-gray-400">
              Loading session messages...
            </div>
          ) : messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto">
              <div className="h-12 w-12 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center mb-3">
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                  />
                </svg>
              </div>
              <h3 className="text-sm font-bold text-gray-800">Orchestra Autonomous Assistant</h3>
              <p className="text-xs text-gray-500 mt-1">
                Ask questions about your project, investigate indexed documents through grounded RAG,
                or request autonomous code generation and AST analysis.
              </p>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto">
              {messages.map((msg, idx) => (
                <MessageBubble
                  key={msg.id ?? idx}
                  message={msg}
                  onRetry={msg.state === "failed" ? handleRetryLast : undefined}
                />
              ))}

              {isExecuting && (
                <div className="flex justify-start mb-6">
                  <div className="rounded-2xl bg-white border border-gray-200 p-4 shadow-sm flex items-center gap-3">
                    <svg className="animate-spin h-4 w-4 text-blue-600" viewBox="0 0 24 24">
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="none"
                      />
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v8H4z"
                      />
                    </svg>
                    <span className="text-xs text-gray-600 font-medium">
                      Routing through LangGraph state machine...
                    </span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Message Input Footer */}
        <div className="p-4 border-t border-gray-200 bg-white flex-shrink-0">
          <div className="max-w-4xl mx-auto">
            <MessageInput onSend={handleSendMessage} disabled={isExecuting} />
          </div>
        </div>
      </div>

      {/* Memory Controls Modal */}
      {activeSessionId && (
        <MemoryModal
          projectId={selectedProject.id}
          sessionId={activeSessionId}
          isOpen={memoryModalOpen}
          onClose={() => setMemoryModalOpen(false)}
        />
      )}
    </div>
  );
}
