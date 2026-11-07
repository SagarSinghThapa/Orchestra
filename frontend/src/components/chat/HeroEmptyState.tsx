"use client";

import React from "react";
import { useRouter } from "next/navigation";

interface HeroEmptyStateProps {
  onSelectPrompt: (promptText: string, intent?: "research" | "developer" | "direct_qa") => void;
}

export function HeroEmptyState({ onSelectPrompt }: HeroEmptyStateProps) {
  const router = useRouter();

  const chips = [
    {
      id: "research",
      label: "Research Assistant",
      iconColor: "#8B7CFF",
      action: () => onSelectPrompt("Synthesize state-of-the-art architectures and literature from indexed sources.", "research"),
      icon: (
        <svg className="w-4 h-4 shrink-0 text-[#8B7CFF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
        </svg>
      ),
    },
    {
      id: "repo",
      label: "Analyze Repository",
      iconColor: "#5146FF",
      action: () => onSelectPrompt("Analyze repository architecture and entry points", "developer"),
      icon: (
        <svg className="w-4 h-4 shrink-0 text-[#5146FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      ),
    },
    {
      id: "code",
      label: "Coding Assistant",
      iconColor: "#8B7CFF",
      action: () => onSelectPrompt("Generate AST-validated implementation for ", "developer"),
      icon: (
        <svg className="w-4 h-4 shrink-0 text-[#8B7CFF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
        </svg>
      ),
    },
    {
      id: "docs",
      label: "Documentation Generator",
      iconColor: "#5146FF",
      action: () => onSelectPrompt("Generate README documentation for this workspace", "developer"),
      icon: (
        <svg className="w-4 h-4 shrink-0 text-[#5146FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
    {
      id: "search",
      label: "Knowledge Search",
      iconColor: "#8B7CFF",
      action: () => onSelectPrompt("Search indexed verified documents for: ", "research"),
      icon: (
        <svg className="w-4 h-4 shrink-0 text-[#8B7CFF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      ),
    },
    {
      id: "evals",
      label: "Evaluate Agents",
      iconColor: "#5146FF",
      action: () => router.push("/evaluations"),
      icon: (
        <svg className="w-4 h-4 shrink-0 text-[#5146FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="w-full max-w-4xl mx-auto py-8 px-4 flex flex-col items-center">
      {/* Stitch Headline & Subtitle */}
      <div className="text-center mb-8">
        <h2 className="text-xs font-semibold text-[#8B7CFF] uppercase tracking-wider mb-2">
          Orchestra Autonomous Assistant
        </h2>
        <h1 className="text-2xl sm:text-[32px] font-semibold text-[#F8F8FC] tracking-tight leading-tight">
          What can I help you accomplish today?
        </h1>
        <p className="text-[14px] sm:text-[15px] text-[#A4A6B8] mt-2.5 max-w-xl mx-auto font-normal">
          Research, analyze, build, and document — all from one intelligent workspace.
        </p>
      </div>

      {/* Task Suggestion Chips ("Start with a task") */}
      <div className="w-full mb-10">
        <p className="text-[11px] uppercase tracking-wider font-semibold text-[#929292] mb-3 text-center">
          Start with a task
        </p>
        <div className="flex flex-wrap items-center justify-center gap-2.5 max-w-3xl mx-auto">
          {chips.map((chip) => (
            <button
              key={chip.id}
              onClick={chip.action}
              className="inline-flex items-center gap-2 h-[38px] px-4 py-2 rounded-lg bg-[#20212B] hover:bg-[#262836] border border-white/[0.08] hover:border-white/20 text-[13px] font-medium text-[#A4A6B8] hover:text-[#F8F8FC] transition-all cursor-pointer shadow-sm active:scale-98"
            >
              {chip.icon}
              <span>{chip.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 3 Feature Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 sm:gap-4 w-full">
        {/* Card 1: Repository Intelligence */}
        <div
          onClick={() => onSelectPrompt("Analyze repository architecture and entry points", "developer")}
          className="p-6 rounded-xl bg-[#20212B] hover:bg-[#242634] border border-white/[0.08] hover:border-white/20 transition-all cursor-pointer flex flex-col justify-between group"
        >
          <div>
            <div className="w-8 h-8 rounded-lg bg-[#5146FF]/10 flex items-center justify-center mb-4 group-hover:bg-[#5146FF]/20 transition-colors">
              <svg className="w-4 h-4 text-[#5146FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-[17px] font-medium text-[#F8F8FC] mb-2">Repository Intelligence</h3>
            <p className="text-[13.5px] text-[#A4A6B8] leading-relaxed">
              Understand repository architecture, dependencies, and potential security risks.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-white/[0.04] flex items-center text-xs text-[#5146FF] font-medium group-hover:translate-x-0.5 transition-transform">
            <span>Explore repository</span>
            <svg className="w-3.5 h-3.5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>

        {/* Card 2: Coding Assistant */}
        <div
          onClick={() => onSelectPrompt("Generate AST-validated implementation for ", "developer")}
          className="p-6 rounded-xl bg-[#20212B] hover:bg-[#242634] border border-white/[0.08] hover:border-white/20 transition-all cursor-pointer flex flex-col justify-between group"
        >
          <div>
            <div className="w-8 h-8 rounded-lg bg-[#8B7CFF]/10 flex items-center justify-center mb-4 group-hover:bg-[#8B7CFF]/20 transition-colors">
              <svg className="w-4 h-4 text-[#8B7CFF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
            </div>
            <h3 className="text-[17px] font-medium text-[#F8F8FC] mb-2">Coding Assistant</h3>
            <p className="text-[13.5px] text-[#A4A6B8] leading-relaxed">
              Generate code, inspect unified diffs, validate changes, and apply approved updates.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-white/[0.04] flex items-center text-xs text-[#8B7CFF] font-medium group-hover:translate-x-0.5 transition-transform">
            <span>Generate code</span>
            <svg className="w-3.5 h-3.5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>

        {/* Card 3: Documentation Generator */}
        <div
          onClick={() => onSelectPrompt("Generate README documentation for this workspace", "developer")}
          className="p-6 rounded-xl bg-[#20212B] hover:bg-[#242634] border border-white/[0.08] hover:border-white/20 transition-all cursor-pointer flex flex-col justify-between group"
        >
          <div>
            <div className="w-8 h-8 rounded-lg bg-[#5146FF]/10 flex items-center justify-center mb-4 group-hover:bg-[#5146FF]/20 transition-colors">
              <svg className="w-4 h-4 text-[#5146FF]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <h3 className="text-[17px] font-medium text-[#F8F8FC] mb-2">Documentation Generator</h3>
            <p className="text-[13.5px] text-[#A4A6B8] leading-relaxed">
              Generate technical documentation, README files, and architecture reports.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-white/[0.04] flex items-center text-xs text-[#5146FF] font-medium group-hover:translate-x-0.5 transition-transform">
            <span>Generate docs</span>
            <svg className="w-3.5 h-3.5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
}
