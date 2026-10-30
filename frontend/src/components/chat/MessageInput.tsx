"use client";

import React, { useRef, useState, useEffect } from "react";

interface MessageInputProps {
  onSend: (content: string) => Promise<void>;
  disabled?: boolean;
}

const MAX_CHAR_LIMIT = 4000;

export function MessageInput({ onSend, disabled = false }: MessageInputProps) {
  const [content, setContent] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [content]);

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const trimmed = content.trim();
    if (!trimmed || disabled) return;

    setContent("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }

    await onSend(trimmed);
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
    <form onSubmit={handleSubmit} className="relative bg-white border border-gray-300 rounded-xl shadow-sm focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-blue-500">
      <textarea
        ref={textareaRef}
        rows={1}
        value={content}
        onChange={(e) => setContent(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={disabled ? "Orchestra is thinking..." : "Ask a question, research documents, or request developer tasks... (Enter to send, Shift+Enter for newline)"}
        maxLength={MAX_CHAR_LIMIT}
        className="w-full resize-none bg-transparent px-4 py-3 text-sm text-gray-900 placeholder-gray-400 focus:outline-none disabled:opacity-60"
      />

      <div className="flex items-center justify-between px-3 pb-2 pt-1 border-t border-gray-100 bg-gray-50/50 rounded-b-xl">
        <div className="text-[11px] text-gray-400">
          <span className={isOverLimit ? "text-red-600 font-bold" : isNearLimit ? "text-amber-600 font-medium" : ""}>
            {content.length.toLocaleString()} / {MAX_CHAR_LIMIT.toLocaleString()} chars
          </span>
        </div>

        <button
          type="submit"
          disabled={disabled || !content.trim() || isOverLimit}
          className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm cursor-pointer"
        >
          {disabled ? (
            <>
              <svg className="animate-spin h-3.5 w-3.5 text-white" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              <span>Executing...</span>
            </>
          ) : (
            <>
              <span>Send</span>
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </>
          )}
        </button>
      </div>
    </form>
  );
}
