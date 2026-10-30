"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/features/auth/AuthContext";
import { ProjectProvider } from "@/features/projects/ProjectContext";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { ProjectSelector } from "@/components/projects/ProjectSelector";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  if (pathname === "/login") {
    return <>{children}</>;
  }

  const navLinks = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/chat", label: "Orchestrator Chat" },
    { href: "/documents", label: "Documents" },
    { href: "/developer/repository", label: "Repository Intel" },
    { href: "/developer", label: "Developer Workspace" },
    { href: "/evaluations", label: "Evaluations" },
    { href: "/settings", label: "Settings" },
  ];

  return (
    <ProtectedRoute>
      <ProjectProvider>
        <div className="flex h-screen overflow-hidden">
          {/* Sidebar */}
          <aside className="w-64 bg-gray-900 text-white flex-shrink-0 flex flex-col justify-between">
            <div>
              <div className="p-4 text-xl font-bold border-b border-gray-800 tracking-tight">
                Orchestra Platform
              </div>
              <nav className="p-4 space-y-1">
                {navLinks.map((link) => {
                  const isActive = pathname === link.href || pathname.startsWith(`${link.href}/`);
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`block px-3 py-2 rounded text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-blue-600 text-white"
                          : "text-gray-300 hover:bg-gray-800 hover:text-white"
                      }`}
                    >
                      {link.label}
                    </Link>
                  );
                })}
              </nav>
            </div>
            <div className="p-4 border-t border-gray-800 text-xs text-gray-500">
              Orchestra v1.0.0
            </div>
          </aside>

          {/* Main Content */}
          <div className="flex flex-col flex-1 overflow-hidden">
            {/* Header */}
            <header className="h-16 bg-white border-b flex items-center justify-between px-6">
              <div id="project-header-slot" className="flex items-center space-x-4">
                <ProjectSelector />
              </div>
              <div className="flex items-center space-x-4">
                {user && (
                  <div className="flex items-center space-x-3">
                    <div className="text-right">
                      <p className="text-sm font-medium text-gray-900">{user.email}</p>
                      <span className="inline-block text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 bg-gray-100 text-gray-700 rounded border">
                        {user.role}
                      </span>
                    </div>
                    <div className="w-9 h-9 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold uppercase shadow-sm">
                      {user.email.charAt(0)}
                    </div>
                    <button
                      onClick={() => logout()}
                      className="text-xs text-gray-500 hover:text-red-600 border border-gray-300 hover:border-red-300 rounded px-2 py-1 transition-colors ml-2"
                    >
                      Sign out
                    </button>
                  </div>
                )}
              </div>
            </header>

            {/* Page Content */}
            <main className="flex-1 overflow-auto p-6 bg-gray-50">{children}</main>
          </div>
        </div>
      </ProjectProvider>
    </ProtectedRoute>
  );
}
