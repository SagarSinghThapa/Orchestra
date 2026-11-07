"use client";

import React, { useState } from "react";
import { Message } from "@/types/chat";
import { SafeMarkdown } from "./SafeMarkdown";
import { AgentResponseCard } from "./AgentResponseCard";

interface MessageBubbleProps {
  message: Message;
  projectId?: number;
  onRetry?: () => void;
}

export function MessageBubble({ message, projectId, onRetry }: MessageBubbleProps) {
  const [showTrace, setShowTrace] = useState(false);

  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[75%] rounded-2xl bg-[#5146FF] text-white px-4.5 py-3 shadow-md">
          <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">{message.content}</p>
          <div className="flex items-center justify-end gap-1.5 mt-1.5 text-[10px] text-white/70">
            {message.state === "sending" && (
              <span className="flex items-center gap-1">
                <svg className="animate-spin h-3 w-3 text-white" viewBox="0 0 24 24">
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
                Sending...
              </span>
            )}
            {message.state === "failed" && (
              <span className="flex items-center gap-1 text-red-200">
                Failed to deliver
                {onRetry && (
                  <button
                    onClick={onRetry}
                    className="underline hover:text-white font-semibold ml-1 cursor-pointer"
                  >
                    Retry
                  </button>
                )}
              </span>
            )}
            {message.created_at && message.state !== "sending" && (
              <span>{new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Assistant Bubble
  const intent = message.intent;
  const executionTrace = message.execution_trace || [];

  return (
    <div className="flex justify-start mb-6">
      <div className="w-full max-w-[90%] sm:max-w-[85%] rounded-2xl bg-[#15151B] border border-white/[0.08] p-5 shadow-lg">
        {/* Intent Route Badge */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            {intent === "direct_qa" && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#5146FF]/15 text-[#8B7CFF] border border-[#5146FF]/30">
                <span className="h-1.5 w-1.5 rounded-full bg-[#5146FF]" />
                Direct Q&A
              </span>
            )}
            {intent === "research" && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                Research Intelligence
              </span>
            )}
            {intent === "developer" && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                Developer Intelligence
              </span>
            )}
            {!intent && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#20212B] text-[#A4A6B8] border border-white/[0.08]">
                Orchestra Assistant
              </span>
            )}
          </div>

          {message.created_at && (
            <span className="text-[10px] text-[#929292]">
              {new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>

        {/* Content */}
        {message.content && (
          <div className="text-sm text-[#F5F5F5] leading-relaxed">
            <SafeMarkdown content={message.content} />
          </div>
        )}

        {/* Structured Results Card */}
        {(message.developer_result || message.research_result) && (
          <AgentResponseCard
            developerResult={message.developer_result}
            researchResult={message.research_result}
            projectId={projectId}
          />
        )}

        {/* Execution Trace Toggle */}
        {executionTrace.length > 0 && (
          <div className="mt-4 pt-3 border-t border-white/[0.06]">
            <button
              onClick={() => setShowTrace(!showTrace)}
              className="inline-flex items-center gap-1.5 text-[11px] text-[#929292] hover:text-[#F8F8FC] font-medium cursor-pointer transition-colors"
            >
              <svg
                className={`h-3 w-3 transform transition-transform ${showTrace ? "rotate-90" : ""}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              <span>{showTrace ? "Hide" : "View"} Execution Trace ({executionTrace.length} steps)</span>
            </button>

            {showTrace && (
              <div className="mt-2 bg-[#20212B] rounded-xl p-3 text-[11px] font-mono text-[#A4A6B8] border border-white/[0.06] space-y-1">
                {executionTrace.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <span className="text-[#929292] select-none">{idx + 1}.</span>
                    <span className="text-[#F5F5F5]">{step}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
