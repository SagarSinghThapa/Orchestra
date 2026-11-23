"use client";

import React from "react";
import { useRouter } from "next/navigation";

interface HeroEmptyStateProps {
  onSelectPrompt: (promptText: string, intent?: "research" | "developer" | "direct_qa") => void;
  composer?: React.ReactNode;
}

export function HeroEmptyState({ onSelectPrompt, composer }: HeroEmptyStateProps) {
  const router = useRouter();

  const chips = [
    {
      id: "research",
      label: "Research Assistant",
      iconColor: "#8B7CFF",
      action: () => onSelectPrompt("Synthesize state-of-the-art architectures and literature from indexed sources.", "research"),
      icon: (
        <svg className="w-3.5 h-3.5 text-[#8B7CFF]" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8" />
          <line x1="21" x2="16.65" y1="16.65" y2="21" />
        </svg>
      ),
    },
    {
      id: "repo",
      label: "Analyze Repository",
      iconColor: "#5146FF",
      action: () => onSelectPrompt("Analyze repository architecture and entry points", "developer"),
      icon: (
        <svg className="w-3.5 h-3.5 text-[#5146FF]" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <rect height="18" rx="2" width="18" x="3" y="3" />
          <line x1="9" x2="9" y1="3" y2="21" />
        </svg>
      ),
    },
    {
      id: "code",
      label: "Coding Assistant",
      iconColor: "#8B7CFF",
      action: () => onSelectPrompt("Generate AST-validated implementation for ", "developer"),
      icon: (
        <svg className="w-3.5 h-3.5 text-[#8B7CFF]" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <polyline points="16 18 22 12 16 6" />
          <polyline points="8 6 2 12 8 18" />
        </svg>
      ),
    },
    {
      id: "docs",
      label: "Documentation Generator",
      iconColor: "#5146FF",
      action: () => onSelectPrompt("Generate README documentation for this workspace", "developer"),
      icon: (
        <svg className="w-3.5 h-3.5 text-[#5146FF]" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" x2="8" y1="13" y2="13" />
          <line x1="16" x2="8" y1="17" y2="17" />
        </svg>
      ),
    },
    {
      id: "search",
      label: "Knowledge Search",
      iconColor: "#8B7CFF",
      action: () => onSelectPrompt("Search indexed verified documents for: ", "research"),
      icon: (
        <svg className="w-3.5 h-3.5 text-[#8B7CFF]" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
        </svg>
      ),
    },
    {
      id: "evals",
      label: "Evaluate Agents",
      iconColor: "#5146FF",
      action: () => router.push("/evaluations"),
      icon: (
        <svg className="w-3.5 h-3.5 text-[#5146FF]" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      ),
    },
  ];

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col justify-center flex-1 my-auto pb-4">
      {/* Center Home Screen Headline & Clean Typography */}
      <div className="text-center mb-8 sm:mb-9">
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

      {/* Primary Composer placed directly in the center */}
      {composer && <div className="w-full mb-2">{composer}</div>}

      {/* Task Suggestion Chips ("Start with a task") */}
      <div className="mt-6 mb-7">
        <div className="text-[11px] uppercase tracking-wider font-semibold text-[#929292] mb-3 text-left">
          Start with a task
        </div>
        <div className="flex flex-nowrap sm:flex-wrap items-center gap-2 overflow-x-auto scrollbar-none pb-1 sm:pb-0 -mx-4 px-4 sm:mx-0 sm:px-0">
          {chips.map((chip) => (
            <button
              key={chip.id}
              onClick={chip.action}
              className="h-[38px] px-4 py-2 rounded-lg bg-[#20212B] hover:bg-[#262836] border border-white/[0.08] hover:border-white/20 text-[13px] font-medium text-[#A4A6B8] hover:text-[#F8F8FC] flex items-center gap-2 transition shrink-0 whitespace-nowrap cursor-pointer shadow-sm active:scale-98"
            >
              {chip.icon}
              <span>{chip.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Feature Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 sm:gap-4 w-full">
        {/* Card 1: Repository Intelligence */}
        <div
          onClick={() => onSelectPrompt("Analyze repository architecture and entry points", "developer")}
          className="p-6 rounded-xl bg-[#20212B] hover:bg-[#242634] border border-white/[0.08] hover:border-white/20 hover:-translate-y-0.5 transition-all duration-200 cursor-pointer flex flex-col justify-between group shadow-sm h-full"
        >
          <div>
            <div className="w-8 h-8 rounded-lg bg-[#5146FF]/10 text-[#5146FF] flex items-center justify-center mb-4 group-hover:bg-[#5146FF]/20 transition-colors">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <rect height="18" rx="2" width="18" x="3" y="3" />
                <line x1="9" x2="9" y1="3" y2="21" />
              </svg>
            </div>
            <h3 className="text-[17px] font-medium text-[#F8F8FC] mb-2 tracking-tight">
              Repository Intelligence
            </h3>
            <p className="text-[13.5px] text-[#A4A6B8] leading-relaxed">
              Understand repository architecture, dependencies, and potential security risks.
            </p>
          </div>
        </div>

        {/* Card 2: Coding Assistant */}
        <div
          onClick={() => onSelectPrompt("Generate AST-validated implementation for ", "developer")}
          className="p-6 rounded-xl bg-[#20212B] hover:bg-[#242634] border border-white/[0.08] hover:border-white/20 hover:-translate-y-0.5 transition-all duration-200 cursor-pointer flex flex-col justify-between group shadow-sm h-full"
        >
          <div>
            <div className="w-8 h-8 rounded-lg bg-[#8B7CFF]/10 text-[#8B7CFF] flex items-center justify-center mb-4 group-hover:bg-[#8B7CFF]/20 transition-colors">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <polyline points="16 18 22 12 16 6" />
                <polyline points="8 6 2 12 8 18" />
              </svg>
            </div>
            <h3 className="text-[17px] font-medium text-[#F8F8FC] mb-2 tracking-tight">
              Coding Assistant
            </h3>
            <p className="text-[13.5px] text-[#A4A6B8] leading-relaxed">
              Generate code, inspect unified diffs, validate changes, and apply approved updates.
            </p>
          </div>
        </div>

        {/* Card 3: Documentation Generator */}
        <div
          onClick={() => onSelectPrompt("Generate README documentation for this workspace", "developer")}
          className="p-6 rounded-xl bg-[#20212B] hover:bg-[#242634] border border-white/[0.08] hover:border-white/20 hover:-translate-y-0.5 transition-all duration-200 cursor-pointer flex flex-col justify-between group shadow-sm md:col-span-2 lg:col-span-1 h-full"
        >
          <div>
            <div className="w-8 h-8 rounded-lg bg-[#5146FF]/10 text-[#5146FF] flex items-center justify-center mb-4 group-hover:bg-[#5146FF]/20 transition-colors">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
                <line x1="16" x2="8" y1="13" y2="13" />
                <line x1="16" x2="8" y1="17" y2="17" />
              </svg>
            </div>
            <h3 className="text-[17px] font-medium text-[#F8F8FC] mb-2 tracking-tight">
              Documentation Generator
            </h3>
            <p className="text-[13.5px] text-[#A4A6B8] leading-relaxed">
              Generate technical documentation, README files, and architecture reports.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
