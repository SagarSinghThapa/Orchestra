"use client";

import React from "react";
import { Card } from "@/components/ui/Card";
import { useAuth } from "@/features/auth/AuthContext";
import { useProject } from "@/features/projects/ProjectContext";
import { getBaseUrl } from "@/services/apiClient";

export default function SettingsPage() {
  const { user } = useAuth();
  const { selectedProject } = useProject();

  let apiUrl = "http://localhost:8000";
  try {
    apiUrl = getBaseUrl();
  } catch {
    // default
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-12">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Platform Settings</h1>
        <p className="text-sm text-gray-500 mt-1">
          System telemetry, active session profile, and security configuration.
        </p>
      </div>

      <Card>
        <h2 className="text-base font-bold text-gray-900 mb-4 border-b pb-2">User Profile &amp; Role</h2>
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <span className="text-gray-400 font-medium">Account ID</span>
            <p className="font-semibold text-gray-800 mt-0.5">#{user?.id || "N/A"}</p>
          </div>
          <div>
            <span className="text-gray-400 font-medium">Email</span>
            <p className="font-semibold text-gray-800 mt-0.5">{user?.email || "N/A"}</p>
          </div>
          <div>
            <span className="text-gray-400 font-medium">RBAC Role</span>
            <p className="mt-0.5">
              <span className="inline-block px-2 py-0.5 rounded font-mono font-bold bg-blue-100 text-blue-800 uppercase text-[10px]">
                {user?.role || "viewer"}
              </span>
            </p>
          </div>
          <div>
            <span className="text-gray-400 font-medium">Active Tenancy</span>
            <p className="font-semibold text-gray-800 mt-0.5">{selectedProject?.name || "None Selected"}</p>
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="text-base font-bold text-gray-900 mb-4 border-b pb-2">Network &amp; Security Architecture</h2>
        <div className="space-y-3 text-xs">
          <div className="flex justify-between items-center py-1 border-b border-gray-100">
            <span className="text-gray-600 font-medium">FastAPI Backend Endpoint</span>
            <span className="font-mono text-gray-800 bg-gray-100 px-2 py-0.5 rounded">{apiUrl}</span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-gray-100">
            <span className="text-gray-600 font-medium">Session Authentication</span>
            <span className="font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded font-semibold">
              httpOnly Cookie (Auto-refresh with mutex)
            </span>
          </div>
          <div className="flex justify-between items-center py-1 border-b border-gray-100">
            <span className="text-gray-600 font-medium">Cross-Origin &amp; CSRF Defense</span>
            <span className="font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded font-semibold">
              X-Orchestra-Request: true Verified
            </span>
          </div>
          <div className="flex justify-between items-center py-1">
            <span className="text-gray-600 font-medium">Mock Mode Status</span>
            <span className="font-mono text-blue-700 bg-blue-50 px-2 py-0.5 rounded font-semibold">
              Decommissioned (Pure Live Backend)
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}
