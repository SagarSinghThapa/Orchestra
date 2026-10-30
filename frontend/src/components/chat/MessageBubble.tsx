"use client";

import React, { useState } from "react";
import { Message } from "@/types/chat";
import { SafeMarkdown } from "./SafeMarkdown";
import { CitationViewer } from "./CitationViewer";

interface MessageBubbleProps {
  message: Message;
  onRetry?: () => void;
}

export function MessageBubble({ message, onRetry }: MessageBubbleProps) {
  const [showTrace, setShowTrace] = useState(false);

  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-[75%] rounded-2xl bg-blue-600 text-white px-4 py-3 shadow-sm">
          <p className="text-sm whitespace-pre-wrap break-words">{message.content}</p>
          <div className="flex items-center justify-end gap-1.5 mt-1.5 text-[10px] text-blue-200">
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
      <div className="max-w-[85%] rounded-2xl bg-white border border-gray-200 p-5 shadow-sm">
        {/* Intent Route Badge */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2">
            {intent === "direct_qa" && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
                Direct Q&A
              </span>
            )}
            {intent === "research" && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Research Intelligence
              </span>
            )}
            {intent === "developer" && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                Developer Intelligence
              </span>
            )}
            {!intent && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-50 text-gray-600 border border-gray-200">
                Assistant
              </span>
            )}
          </div>

          {message.created_at && (
            <span className="text-[10px] text-gray-400">
              {new Date(message.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          )}
        </div>

        {/* Content */}
        <SafeMarkdown content={message.content} />

        {/* Citations */}
        {message.research_result && (
          <CitationViewer researchResult={message.research_result} />
        )}

        {/* Execution Trace Toggle */}
        {executionTrace.length > 0 && (
          <div className="mt-4 pt-3 border-t border-gray-100">
            <button
              onClick={() => setShowTrace(!showTrace)}
              className="inline-flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-800 font-medium cursor-pointer"
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
              <div className="mt-2 bg-gray-50 rounded p-2.5 text-[11px] font-mono text-gray-600 border border-gray-200 space-y-1">
                {executionTrace.map((step, idx) => (
                  <div key={idx} className="flex items-start gap-1.5">
                    <span className="text-gray-400 select-none">{idx + 1}.</span>
                    <span>{step}</span>
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
