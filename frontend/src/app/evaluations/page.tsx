"use client";

import React from "react";
import { Card } from "@/components/ui/Card";

export default function EvaluationsPage() {
  const plannedPillars = [
    {
      title: "RAG Faithfulness & Hallucination Scoring",
      badge: "DeepEval / RAGAS",
      desc: "Automated verification comparing orchestrator research claims against verbatim chunk citations to guarantee zero ungrounded assertions.",
      status: "Scheduled",
    },
    {
      title: "Conversational Context Retention",
      badge: "Memory Benchmarks",
      desc: "Deterministic test harness assessing summary compression quality, multi-turn entity tracking, and sliding-window boundary limits.",
      status: "Scheduled",
    },
    {
      title: "AST Syntax & Tool Execution Safety",
      badge: "Code Benchmarks",
      desc: "Continuous evaluation of generated Python and TypeScript diffs against tree-sitter AST parsers and subprocess sandbox boundaries.",
      status: "Scheduled",
    },
    {
      title: "Latency & Token Economics",
      badge: "Telemetry Auditing",
      desc: "Real-time tracking of request-wide LLM token budgets, gateway response latencies, and checkpoint storage serialization efficiency.",
      status: "Scheduled",
    },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Model &amp; Agent Evaluations</h1>
        <p className="text-sm text-gray-500 mt-1">
          Automated benchmarking suite for multi-agent intelligence, faithfulness, and safety telemetry.
        </p>
      </div>

      {/* Honest Phase 11 Roadmap Banner */}
      <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-6 shadow-xs">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-blue-600 text-white rounded-lg">
            <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
          </div>
          <div>
            <span className="inline-block px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-100 text-blue-800 mb-1">
              Phase 11 Preview — Model &amp; Agent Evaluations
            </span>
            <h2 className="text-base font-bold text-gray-900">
              Evaluations Engine Scheduled for Phase 11
            </h2>
            <p className="text-xs text-gray-600 mt-1 leading-relaxed">
              Automated hallucination rate benchmarks, RAG faithfulness metrics, coding AST validation telemetry,
              and latency tracking are scheduled for implementation in Phase 11. Mock metrics have been completely
              decommissioned to ensure production data integrity.
            </p>
          </div>
        </div>
      </div>

      {/* Planned Pillars */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-4">
          Planned Evaluation Pillars
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {plannedPillars.map((p, idx) => (
            <Card key={idx}>
              <div className="flex flex-col h-full justify-between">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                      {p.badge}
                    </span>
                    <span className="text-[10px] font-semibold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
                      {p.status}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-gray-900 mb-1.5">{p.title}</h3>
                  <p className="text-xs text-gray-500 leading-relaxed">{p.desc}</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
