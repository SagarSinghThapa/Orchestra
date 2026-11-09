"use client";

import React, { useRef, useState, useEffect } from "react";
import Link from "next/link";

interface MessageInputProps {
  onSend: (content: string, options?: { forced_intent?: "research" | "developer" | "direct_qa" }) => Promise<void>;
  disabled?: boolean;
  activeProjectName?: string;
  forcedIntent?: "research" | "developer" | "direct_qa" | null;
  onClearForcedIntent?: () => void;
  value?: string;
  onChange?: (val: string) => void;
  isExecuting?: boolean;
  onStop?: () => void;
}

const MAX_CHAR_LIMIT = 4000;

export function MessageInput({
  onSend,
  disabled = false,
  activeProjectName,
  forcedIntent,
  onClearForcedIntent,
  value,
  onChange,
  isExecuting = false,
  onStop,
}: MessageInputProps) {
  const [internalContent, setInternalContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isControlled = value !== undefined;
  const content = isControlled ? value : internalContent;

  const handleContentChange = (newVal: string) => {
    if (isControlled && onChange) {
      onChange(newVal);
    } else {
      setInternalContent(newVal);
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 220)}px`;
    }
  }, [content]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = content.trim();
    if (!trimmed || disabled) return;

    handleContentChange("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    await onSend(trimmed, {
      forced_intent: forcedIntent || undefined,
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isNearLimit = content.length > 3500;
  const isOverLimit = content.length > MAX_CHAR_LIMIT;

  return (
    <form
      onSubmit={handleSubmit}
      className="relative w-full min-h-[140px] sm:min-h-[150px] bg-[#20212B] border border-white/[0.12] rounded-[18px] p-3.5 sm:p-5 shadow-2xl focus-within:border-white/20 flex flex-col justify-between transition-colors"
    >
      {/* Active Mode / Intent Pill Banner if forced */}
      {forcedIntent && (
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-white/[0.06]">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold text-[#8B7CFF] uppercase tracking-wider">
              Forced Intent:
            </span>
            <span className="px-2 py-0.5 rounded bg-[#5146FF]/20 text-[#8B7CFF] text-xs font-medium border border-[#5146FF]/30">
              {forcedIntent === "research"
                ? "Research Intelligence"
                : forcedIntent === "developer"
                ? "Developer Intelligence"
                : "Direct Q&A"}
            </span>
          </div>
          {onClearForcedIntent && (
            <button
              type="button"
              onClick={onClearForcedIntent}
              className="text-[11px] text-[#929292] hover:text-[#F8F8FC] underline cursor-pointer"
            >
              Reset to Auto-Route
            </button>
          )}
        </div>
      )}

      {/* Main Textarea */}
      <textarea
        ref={textareaRef}
        rows={2}
        value={content}
        onChange={(e) => handleContentChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={
          disabled
            ? "Routing through LangGraph state machine..."
            : "Ask Orchestra anything..."
        }
        maxLength={MAX_CHAR_LIMIT}
        className="w-full bg-transparent border-0 text-[#F5F5F5] placeholder-[#929292] text-sm sm:text-base leading-relaxed resize-none p-0 focus:ring-0 focus:outline-none disabled:opacity-60"
      />

      {/* Bottom Action Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-3 mt-2 border-t border-white/[0.06]">
        {/* Left Toolbar Controls */}
        <div className="flex items-center gap-2 sm:gap-3 text-xs text-[#A4A6B8]">
          {/* Attach Button: Navigates to Documents workspace for real knowledge ingestion */}
          <Link
            href="/documents"
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-[#A4A6B8] hover:text-[#F8F8FC] transition border border-white/[0.06] cursor-pointer"
            title="Upload and index documents in Documents workspace"
          >
            <svg className="w-3.5 h-3.5 text-[#929292]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
            <span className="hidden sm:inline">Attach</span>
          </Link>

          {/* Project Pill */}
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.04] text-[#A4A6B8] border border-white/[0.06] max-w-[180px]">
            <svg className="w-3.5 h-3.5 text-[#8B7CFF] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <span className="truncate text-[11px] font-medium">{activeProjectName || "Workspace"}</span>
          </div>

          {/* Search Button */}
          <button
            type="button"
            onClick={() => {
              if (forcedIntent === "research") {
                if (onClearForcedIntent) onClearForcedIntent();
              } else {
                handleContentChange(content.startsWith("Search ") ? content : `Search ${content}`);
              }
            }}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg transition border cursor-pointer ${
              forcedIntent === "research"
                ? "bg-[#5146FF]/20 text-[#8B7CFF] border-[#5146FF]/40"
                : "bg-white/[0.04] hover:bg-white/[0.08] text-[#A4A6B8] hover:text-[#F8F8FC] border-white/[0.06]"
            }`}
            title="Search verified citations"
          >
            <svg className="w-3.5 h-3.5 text-[#929292]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span className="hidden sm:inline">Search</span>
          </button>

          {/* Server Orchestration Engine Status Pill (Truthful non-interactive indicator) */}
          <div
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white/[0.04] text-[#A4A6B8] border border-white/[0.06] text-xs select-none"
            title="Server Orchestration Engine: Managed by operator environment configuration"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[#5146FF]" />
            <span className="text-[11px] font-medium text-[#F8F8FC]">Orchestra AI</span>
          </div>
        </div>

        {/* Right Controls: Char count + Shortcut + Send */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono text-[#929292]">
            <kbd className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/[0.08] text-[10px] text-[#A4A6B8]">
              ⌘ Enter
            </kbd>
            <span className={isOverLimit ? "text-rose-400 font-bold" : isNearLimit ? "text-amber-400" : ""}>
              {content.length.toLocaleString()} / {MAX_CHAR_LIMIT.toLocaleString()}
            </span>
          </div>

          {/* Stop / Send Button */}
          {isExecuting && onStop ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop generating"
              className="w-8 h-8 rounded-lg bg-[#20212B] hover:bg-[#282836] border border-white/[0.18] text-[#F8F8FC] flex items-center justify-center transition active:scale-95 shadow-md cursor-pointer group"
              title="Stop generating"
            >
              <span className="w-2.5 h-2.5 bg-rose-500 rounded-xs group-hover:scale-110 transition-transform" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={disabled || !content.trim() || isOverLimit}
              aria-label="Send"
              className="w-8 h-8 rounded-lg bg-[#5146FF] hover:bg-[#4338e8] disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center justify-center transition active:scale-95 shadow-sm cursor-pointer"
            >
              <span className="sr-only">Send</span>
              {disabled ? (
                <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              ) : (
                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                </svg>
              )}
            </button>
          )}
        </div>
      </div>
    </form>
  );
}
