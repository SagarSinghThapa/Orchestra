"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/AuthContext";
import { ProjectProvider } from "@/features/projects/ProjectContext";
import { ProtectedRoute } from "@/features/auth/ProtectedRoute";
import { ProjectSelector } from "@/components/projects/ProjectSelector";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const handleNewChat = useCallback(() => {
    router.push("/chat");
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("orchestra-new-chat"));
    }
  }, [router]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        handleNewChat();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleNewChat]);

  if (pathname === "/login") {
    return <>{children}</>;
  }

  const navLinks = [
    {
      href: "/chat",
      label: "Recent Conversations",
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      ),
    },
    {
      href: "/projects",
      label: "Projects",
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z" />
        </svg>
      ),
    },
    {
      href: "/documents",
      label: "Documents & Artifacts",
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" x2="8" y1="13" y2="13" />
          <line x1="16" x2="8" y1="17" y2="17" />
        </svg>
      ),
    },
    {
      href: "/developer/repository",
      label: "Repository Intelligence",
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <rect height="18" rx="2" width="18" x="3" y="3" />
          <line x1="9" x2="9" y1="3" y2="21" />
        </svg>
      ),
    },
    {
      href: "/evaluations",
      label: "Evaluations",
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      ),
    },
    {
      href: "/settings",
      label: "Settings",
      icon: (
        <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83-2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      ),
    },
  ];

  const handleNavClick = (href: string, e: React.MouseEvent) => {
    setMobileSidebarOpen(false);
    if (href === "/chat") {
      if (pathname === "/chat") {
        e.preventDefault();
        window.dispatchEvent(new CustomEvent("orchestra-toggle-recent-conversations"));
      } else {
        setTimeout(() => {
          window.dispatchEvent(new CustomEvent("orchestra-open-recent-conversations"));
        }, 100);
      }
    }
  };

  return (
    <ProtectedRoute>
      <ProjectProvider>
        <div className="flex h-screen w-full bg-[#101014] text-[#F5F5F5] font-sans antialiased overflow-hidden relative selection:bg-[#5146FF]/30 selection:text-white">
          {/* Mobile Drawer Backdrop */}
          {mobileSidebarOpen && (
            <div
              className="fixed inset-0 bg-black/70 backdrop-blur-sm z-30 md:hidden transition-opacity duration-300"
              onClick={() => setMobileSidebarOpen(false)}
            />
          )}

          {/* BEGIN: Left Navigation Sidebar (Pure Black #000000, 250px) */}
          <aside
            id="main-sidebar"
            className={`fixed inset-y-0 left-0 z-40 w-[250px] shrink-0 bg-[#000000] border-r border-[#242424] flex flex-col justify-between select-none h-full transform transition-transform duration-200 ease-in-out md:static md:translate-x-0 ${
              mobileSidebarOpen ? "translate-x-0" : "-translate-x-full"
            }`}
          >
            {/* Top Brand & Navigation */}
            <div className="flex flex-col pt-4 px-3 space-y-4">
              {/* Orchestra Brand Header */}
              <div className="flex items-center justify-between px-2 pb-1">
                <Link href="/chat" className="flex items-center gap-2.5">
                  <div className="w-7 h-7 rounded-lg bg-[#5146FF] flex items-center justify-center text-white shadow-sm shadow-[#5146FF]/30 shrink-0">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24">
                      <circle cx="12" cy="12" r="3" />
                      <path d="M12 3v3m0 12v3M3 12h3m12 0h3m-2.6-6.4-2.1 2.1m-6.6 6.6-2.1 2.1m10.8 0-2.1-2.1m-6.6-6.6-2.1-2.1" />
                    </svg>
                  </div>
                  <span className="text-[17px] font-semibold tracking-tight text-white">Orchestra</span>
                </Link>
                {/* Mobile close button */}
                <button
                  aria-label="Close sidebar"
                  className="md:hidden p-1.5 rounded-lg text-[#929292] hover:text-white hover:bg-white/[0.06]"
                  onClick={() => setMobileSidebarOpen(false)}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              </div>

              {/* New Chat CTA Button */}
              <button
                type="button"
                onClick={handleNewChat}
                className="w-full h-10 px-3 bg-[#202020] hover:bg-[#282828] text-white border border-[#5146FF]/40 rounded-lg flex items-center justify-between transition-colors group shadow-sm shadow-[#5146FF]/10 cursor-pointer"
              >
                <div className="flex items-center gap-2.5">
                  <svg className="w-4 h-4 text-[#5146FF]" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path d="M12 4.5v15m7.5-7.5h-15" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="text-[13px] font-medium text-white">New Chat</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#5146FF]" />
                  <kbd className="px-1.5 py-0.5 rounded bg-black/60 text-[10px] font-mono text-[#929292] border border-[#242424]">
                    ⌘K
                  </kbd>
                </div>
              </button>

              {/* Main Navigation Items */}
              <nav className="space-y-1 pt-1">
                {navLinks.map((link) => {
                  const isActive =
                    link.href === "/chat"
                      ? pathname === "/chat" || pathname === "/" || pathname === "/dashboard"
                      : pathname === link.href || pathname.startsWith(`${link.href}/`);
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      onClick={(e) => handleNavClick(link.href, e)}
                      className={`flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[14px] font-medium transition group ${
                        isActive
                          ? "bg-[#202020] text-[#FFFFFF]"
                          : "text-[#A4A6B8] hover:bg-[#202020]/70 hover:text-[#FFFFFF]"
                      }`}
                    >
                      <span className={`${isActive ? "text-[#5146FF]" : "text-[#929292] group-hover:text-white"} transition-colors`}>
                        {link.icon}
                      </span>
                      <span>{link.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>

            {/* Bottom User Profile Section on Pure Solid Black */}
            <div className="p-3 border-t border-[#242424] bg-[#000000]">
              {user && (
                <div className="flex items-center justify-between p-1.5 rounded-lg hover:bg-[#202020] transition">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="relative shrink-0">
                      <div className="w-8 h-8 rounded-full bg-[#20212B] border border-[#242424] flex items-center justify-center text-xs font-semibold text-white uppercase">
                        {user.email.substring(0, 2)}
                      </div>
                      <span className="w-2 h-2 rounded-full bg-emerald-500 border border-black absolute bottom-0 right-0" />
                    </div>
                    <div className="flex flex-col min-w-0">
                      <span className="text-xs font-medium text-[#F5F5F5] truncate max-w-[120px]">{user.email}</span>
                      <span className="text-[11px] text-[#929292] truncate capitalize">Online · {user.role}</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => logout()}
                    aria-label="Sign out"
                    title="Sign out"
                    className="text-xs text-[#929292] hover:text-red-400 p-1 rounded hover:bg-white/[0.04] transition"
                  >
                    Sign out
                  </button>
                </div>
              )}
            </div>
          </aside>
          {/* END: Left Navigation Sidebar */}

          {/* BEGIN: Main Workspace Canvas & Content Area */}
          <div className="flex-1 flex flex-col h-full overflow-hidden workspace-gradient-bg min-w-0">
            {/* Sleek, Minimal Top Bar */}
            <header className="h-14 px-4 sm:px-8 flex items-center justify-between border-b border-[#242424]/80 bg-[#101014]/90 backdrop-blur-md shrink-0 z-10">
              {/* Left: Mobile toggle + Project selector */}
              <div className="flex items-center gap-2 sm:gap-3">
                <button
                  aria-label="Open navigation menu"
                  className="md:hidden p-2 text-[#929292] hover:text-white hover:bg-white/[0.04] rounded-lg transition"
                  onClick={() => setMobileSidebarOpen(true)}
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <line x1="3" x2="21" y1="12" y2="12" />
                    <line x1="3" x2="21" y1="6" y2="6" />
                    <line x1="3" x2="21" y1="18" y2="18" />
                  </svg>
                </button>
                <div id="project-header-slot">
                  <ProjectSelector />
                </div>
                {/* Aggregate Status Indicator */}
                <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 text-[11px] font-medium text-[#A4A6B8]">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>Connected</span>
                </div>
              </div>

              {/* Right: Notifications / Settings */}
              <div className="flex items-center gap-1.5 sm:gap-2">
                <Link
                  href="/settings"
                  className="p-2 text-[#929292] hover:text-white rounded-lg hover:bg-white/[0.04] transition"
                  title="Workspace Settings"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="3" />
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                  </svg>
                </Link>
              </div>
            </header>

            {/* Page Content */}
            <main className="flex-1 overflow-auto">{children}</main>
          </div>
          {/* END: Main Workspace Canvas */}
        </div>
      </ProjectProvider>
    </ProtectedRoute>
  );
}
