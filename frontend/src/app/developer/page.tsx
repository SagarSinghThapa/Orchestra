"use client";

import React from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { ClassificationBanner } from "@/components/developer/ClassificationBanner";

export default function DeveloperIntelligencePage() {
  const tools = [
    {
      title: "Autonomous Coding Assistant",
      href: "/developer/coding",
      desc: "Two-stage verified code synthesis: generate, review unified diffs with AST validation, and apply to workspace disk.",
      badge: "Preview & Apply",
      badgeColor: "bg-blue-100 text-blue-800",
    },
    {
      title: "Repository Intelligence",
      href: "/developer/repository",
      desc: "Deep structural analysis of workspace architecture, dependencies, frameworks, and security risks.",
      badge: "Inspection",
      badgeColor: "bg-emerald-100 text-emerald-800",
    },
    {
      title: "Documentation Generator",
      href: "/developer/documentation",
      desc: "Automated synthesis of README, architecture guides, and API documentation with safe file write guards.",
      badge: "Doc Gen",
      badgeColor: "bg-purple-100 text-purple-800",
    },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Developer Intelligence Workspace</h1>
        <p className="text-sm text-gray-500 mt-1">
          Specialized developer subsystems for autonomous code synthesis, repository mapping, and technical documentation.
        </p>
      </div>

      <ClassificationBanner />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {tools.map((t) => (
          <Card key={t.href}>
            <div className="flex flex-col h-full justify-between">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${t.badgeColor}`}>
                    {t.badge}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-gray-900 mb-2">{t.title}</h2>
                <p className="text-xs text-gray-500 leading-relaxed mb-4">{t.desc}</p>
              </div>

              <Link
                href={t.href}
                className="w-full text-center py-2 px-3 rounded-lg text-xs font-semibold bg-gray-900 text-white hover:bg-gray-800 transition-colors shadow-sm"
              >
                Launch Workspace →
              </Link>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
