"use client";

import React from "react";
import { Card } from "@/components/ui/Card";
import { useAuth } from "@/features/auth/AuthContext";
import { useProject } from "@/features/projects/ProjectContext";
import { getBaseUrl } from "@/services/apiClient";

export default function SettingsPage() {
  const { user } = useAuth();
  const { selectedProject } = useProject();

  let apiUrl = "Same-Origin (Reverse Proxy)";
  try {
    const base = getBaseUrl();
    apiUrl = base ? base : "Same-Origin (Reverse Proxy)";
  } catch {
    // default
  }

  return (
    <div className="p-6 sm:p-8 space-y-6 max-w-4xl mx-auto pb-12">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-[#F8F8FC] tracking-tight">
          Platform Settings
        </h1>
        <p className="text-xs sm:text-sm text-[#A4A6B8] mt-1">
          System telemetry, active session profile, and security configuration.
        </p>
      </div>

      <Card>
        <h2 className="text-sm font-semibold text-[#F8F8FC] mb-4 border-b border-white/[0.06] pb-2.5">
          User Profile &amp; Role
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div>
            <span className="text-[#929292] font-medium">Account ID</span>
            <p className="font-semibold text-[#F8F8FC] mt-0.5">#{user?.id || "N/A"}</p>
          </div>
          <div>
            <span className="text-[#929292] font-medium">Email</span>
            <p className="font-semibold text-[#F8F8FC] mt-0.5">{user?.email || "N/A"}</p>
          </div>
          <div>
            <span className="text-[#929292] font-medium">RBAC Role</span>
            <p className="mt-0.5">
              <span className="inline-block px-2.5 py-0.5 rounded-md font-mono font-bold bg-[#5146FF]/20 text-[#8B7CFF] border border-[#5146FF]/30 uppercase text-[10px]">
                {user?.role || "viewer"}
              </span>
            </p>
          </div>
          <div>
            <span className="text-[#929292] font-medium">Active Tenancy</span>
            <p className="font-semibold text-[#F8F8FC] mt-0.5">{selectedProject?.name || "None Selected"}</p>
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="text-sm font-semibold text-[#F8F8FC] mb-4 border-b border-white/[0.06] pb-2.5">
          Network &amp; Security Architecture
        </h2>
        <div className="space-y-3 text-xs">
          <div className="flex flex-wrap justify-between items-center py-2 border-b border-white/[0.04]">
            <span className="text-[#A4A6B8]">FastAPI Backend Endpoint</span>
            <span className="font-mono text-[#F8F8FC] bg-[#15151B] px-2.5 py-1 rounded-md border border-white/[0.06]">{apiUrl}</span>
          </div>
          <div className="flex flex-wrap justify-between items-center py-2 border-b border-white/[0.04]">
            <span className="text-[#A4A6B8]">Session Authentication</span>
            <span className="font-mono text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 rounded-md font-medium">
              httpOnly Cookie (Auto-refresh with mutex)
            </span>
          </div>
          <div className="flex flex-wrap justify-between items-center py-2 border-b border-white/[0.04]">
            <span className="text-[#A4A6B8]">Cross-Origin &amp; CSRF Defense</span>
            <span className="font-mono text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 rounded-md font-medium">
              X-Orchestra-Request: true Verified
            </span>
          </div>
          <div className="flex flex-wrap justify-between items-center py-2 border-b border-white/[0.04]">
            <span className="text-[#A4A6B8]">LLM Provider Configuration</span>
            <span className="font-mono text-[#8B7CFF] bg-[#5146FF]/15 border border-[#5146FF]/30 px-2.5 py-1 rounded-md font-medium">
              Configured (Operator Environment Controlled)
            </span>
          </div>
          <div className="flex flex-wrap justify-between items-center py-2 border-b border-white/[0.04]">
            <span className="text-[#A4A6B8]">Embedding Vector Engine</span>
            <span className="font-mono text-[#8B7CFF] bg-[#5146FF]/15 border border-[#5146FF]/30 px-2.5 py-1 rounded-md font-medium">
              Qdrant 1536-dim Dense Index
            </span>
          </div>
          <div className="flex flex-wrap justify-between items-center py-2">
            <span className="text-[#A4A6B8]">Mock Mode Status</span>
            <span className="font-mono text-emerald-400 bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 rounded-md font-medium">
              Decommissioned (Pure Live Backend)
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}
