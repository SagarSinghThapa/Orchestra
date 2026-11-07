"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useProject } from "@/features/projects/ProjectContext";
import { SessionSidebar } from "@/components/chat/SessionSidebar";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { MessageInput } from "@/components/chat/MessageInput";
import { MemoryModal } from "@/components/chat/MemoryModal";
import { HeroEmptyState } from "@/components/chat/HeroEmptyState";
import { IntentType, Message, OrchestratorRequest, OrchestratorResponse, SessionItem } from "@/types/chat";
import { api } from "@/services/apiClient";

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
  const [forcedIntent, setForcedIntent] = useState<IntentType | null>(null);
  const [inputContent, setInputContent] = useState<string>("");
  const [recentDrawerOpen, setRecentDrawerOpen] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const skipFetchSessionIdRef = useRef<number | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isExecuting]);

  // Global custom event listeners for sidebar actions
  useEffect(() => {
    const handleNewChatEvent = () => {
      skipFetchSessionIdRef.current = null;
      setActiveSessionId(null);
      setMessages([]);
      setErrorBanner(null);
      setForcedIntent(null);
      setInputContent("");
    };

    const handleToggleDrawer = () => setRecentDrawerOpen((prev) => !prev);
    const handleOpenDrawer = () => setRecentDrawerOpen(true);

    window.addEventListener("orchestra-new-chat", handleNewChatEvent);
    window.addEventListener("orchestra-toggle-recent-conversations", handleToggleDrawer);
    window.addEventListener("orchestra-open-recent-conversations", handleOpenDrawer);

    return () => {
      window.removeEventListener("orchestra-new-chat", handleNewChatEvent);
      window.removeEventListener("orchestra-toggle-recent-conversations", handleToggleDrawer);
      window.removeEventListener("orchestra-open-recent-conversations", handleOpenDrawer);
    };
  }, []);

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
          if (data.length > 0) {
            setActiveSessionId((prev) => (prev === null ? data[0].id : prev));
          }
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
    if (skipFetchSessionIdRef.current === activeSessionId) {
      skipFetchSessionIdRef.current = null;
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
    skipFetchSessionIdRef.current = null;
    setActiveSessionId(id);
    setRecentDrawerOpen(false);
  };

  const handleNewChat = () => {
    skipFetchSessionIdRef.current = null;
    setActiveSessionId(null);
    setMessages([]);
    setErrorBanner(null);
    setForcedIntent(null);
    setInputContent("");
    setRecentDrawerOpen(false);
  };

  const handleSelectPromptFromHero = (promptText: string, intent?: IntentType) => {
    setInputContent(promptText);
    if (intent) {
      setForcedIntent(intent);
    }
  };

  const handleSendMessage = useCallback(
    async (
      content: string,
      options?: { forced_intent?: IntentType }
    ) => {
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
        const payload: OrchestratorRequest & {
          forced_intent?: IntentType;
          developer_params?: Record<string, unknown>;
        } = {
          prompt: content,
          session_id: activeSessionId,
          forced_intent: options?.forced_intent,
        };

        if (options?.forced_intent === "developer") {
          payload.developer_params = { task_type: "code_gen", mode: "preview" };
        }

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
          skipFetchSessionIdRef.current = response.session_id;
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
    },
    [selectedProject, isExecuting, activeSessionId]
  );

  const handleRetryLast = useCallback(async () => {
    const lastUserMsg = [...messages].reverse().find((m) => m.role === "user");
    if (lastUserMsg) {
      setMessages((prev) => prev.slice(0, prev.length - 1));
      await handleSendMessage(lastUserMsg.content, {
        forced_intent: forcedIntent || undefined,
      });
    }
  }, [messages, handleSendMessage, forcedIntent]);

  if (!selectedProject) {
    return (
      <div className="flex-1 flex items-center justify-center p-6 workspace-gradient-bg min-h-[calc(100vh-3.5rem)]">
        <div className="max-w-md w-full p-8 rounded-2xl bg-[#20212B] border border-white/[0.08] text-center shadow-2xl">
          <div className="w-12 h-12 rounded-xl bg-[#5146FF]/10 text-[#8B7CFF] flex items-center justify-center mx-auto mb-4 border border-[#5146FF]/20">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-[#F8F8FC]">No Project Selected</h2>
          <p className="text-xs text-[#A4A6B8] mt-2 leading-relaxed">
            Please select or create an active project workspace from the top navigation to begin an Orchestrator session.
          </p>
        </div>
      </div>
    );
  }

  const composerElement = (
    <MessageInput
      onSend={handleSendMessage}
      disabled={isExecuting}
      activeProjectName={selectedProject.name}
      forcedIntent={forcedIntent}
      onClearForcedIntent={() => setForcedIntent(null)}
      value={inputContent}
      onChange={setInputContent}
    />
  );

  return (
    <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden workspace-gradient-bg relative">
      {/* Slide-over Recent Conversations Drawer (On Demand, Not Permanent Sidebar) */}
      <SessionSidebar
        isOpen={recentDrawerOpen}
        onClose={() => setRecentDrawerOpen(false)}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        loading={loadingSessions}
      />

      {/* Main Single Unified Workspace */}
      <div className="flex-1 flex flex-col h-full overflow-hidden min-w-0">
        {/* Error Banner */}
        {errorBanner && (
          <div className="px-6 py-2.5 bg-rose-500/15 border-b border-rose-500/30 text-xs text-rose-300 flex items-center justify-between z-10 shrink-0">
            <span>{errorBanner}</span>
            <button
              onClick={() => setErrorBanner(null)}
              className="text-rose-400 hover:text-rose-200 font-bold ml-4 cursor-pointer"
            >
              ✕
            </button>
          </div>
        )}

        {/* Viewport Area */}
        {loadingMessages ? (
          <div className="flex-1 flex items-center justify-center text-xs text-[#929292]">
            <div className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4 text-[#5146FF]" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>Loading session history...</span>
            </div>
          </div>
        ) : messages.length === 0 ? (
          /* Authoritative Stitch Empty State Hero with Centered Composer */
          <main className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 sm:py-8 flex flex-col items-center">
            <HeroEmptyState
              onSelectPrompt={handleSelectPromptFromHero}
              composer={composerElement}
            />
          </main>
        ) : (
          /* Active Conversation Thread View */
          <>
            {/* Minimal Sub-header: Clean Session Kicker & Memory Telemetry */}
            <div className="px-4 sm:px-8 py-2.5 border-b border-white/[0.06] bg-[#101014]/60 backdrop-blur-md flex items-center justify-between shrink-0 z-10">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setRecentDrawerOpen(true)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium text-[#A4A6B8] hover:text-[#F8F8FC] bg-[#20212B] hover:bg-[#262836] border border-white/[0.08] transition cursor-pointer"
                  title="View conversation history"
                >
                  <svg className="w-3.5 h-3.5 text-[#8B7CFF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span>Recent Conversations ({sessions.length})</span>
                </button>
                <span className="text-xs text-[#929292] font-mono">
                  {activeSessionId ? `Session #${activeSessionId}` : "Current Session"}
                </span>
              </div>

              <div className="flex items-center gap-2">
                {activeSessionId && (
                  <button
                    type="button"
                    onClick={() => setMemoryModalOpen(true)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-white/[0.08] bg-[#20212B] hover:bg-[#262836] text-xs font-medium text-[#A4A6B8] hover:text-[#F8F8FC] shadow-sm transition-colors cursor-pointer"
                  >
                    <svg className="h-3.5 w-3.5 text-[#8B7CFF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

            {/* Messages Scroll Area */}
            <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6">
              <div className="max-w-4xl mx-auto space-y-4">
                {messages.map((msg, idx) => (
                  <MessageBubble
                    key={msg.id ?? idx}
                    message={msg}
                    projectId={selectedProject.id}
                    onRetry={msg.state === "failed" ? handleRetryLast : undefined}
                  />
                ))}

                {isExecuting && (
                  <div className="flex justify-start mb-6">
                    <div className="rounded-2xl bg-[#15151B] border border-white/[0.08] p-4 shadow-lg flex items-center gap-3">
                      <svg className="animate-spin h-4 w-4 text-[#5146FF]" viewBox="0 0 24 24">
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
                      <span className="text-xs text-[#A4A6B8] font-medium">
                        Routing through LangGraph state machine...
                      </span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Pinned Bottom Message Input Footer */}
            <div className="p-4 sm:p-5 border-t border-white/[0.08] bg-[#101014]/95 backdrop-blur-md flex-shrink-0">
              <div className="max-w-4xl mx-auto">{composerElement}</div>
            </div>
          </>
        )}
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
