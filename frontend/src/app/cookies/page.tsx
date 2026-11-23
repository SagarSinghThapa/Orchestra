"use client";

import React from "react";
import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { usePrivacy } from "@/features/privacy/PrivacyContext";
import { getPolicyGovernanceStatus } from "@/features/privacy/governance";

export default function CookiePolicyPage() {
  const { openPreferences } = usePrivacy();
  const governance = getPolicyGovernanceStatus();

  return (
    <div className="min-h-screen bg-[#101014] text-[#F5F5F5] py-12 px-4 sm:px-8">
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Navigation link */}
        <div className="flex items-center justify-between">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 text-xs font-medium text-[#8B7CFF] hover:text-[#A599FF] transition"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Back to Orchestra
          </Link>
          <Link
            href="/privacy"
            className="text-xs font-medium text-[#A4A6B8] hover:text-white transition"
          >
            View Privacy Policy &rarr;
          </Link>
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="space-y-2">
            <div className="flex flex-col sm:flex-row sm:items-baseline sm:gap-4">
              <h1 className="text-3xl sm:text-4xl font-extrabold text-[#F8F8FC] tracking-tight">
                Cookie Policy
              </h1>
              <span className="text-xs font-mono text-[#A4A6B8]">
                Effective Date: {governance.effectiveDate}
              </span>
            </div>
            <p className="text-sm text-[#A4A6B8]">
              Empirical inventory of cookies and browser storage technologies.
            </p>
          </div>
          <button
            type="button"
            onClick={openPreferences}
            className="self-start sm:self-auto px-4 py-2 text-xs sm:text-sm font-medium rounded-lg bg-[#5146FF] hover:bg-[#4338CA] text-white shadow-md transition focus:outline-none focus:ring-2 focus:ring-[#5146FF] focus:ring-offset-2 focus:ring-offset-[#101014]"
          >
            Open Cookie Preferences
          </button>
        </div>

        {/* Draft Notice Banner (strictly enforced until 3-gate owner sign-off) */}
        {governance.isDraft && (
          <div
            role="alert"
            className="p-4 sm:p-5 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs sm:text-sm space-y-1"
          >
            <div className="flex items-center gap-2 font-bold font-mono uppercase tracking-wider text-amber-300">
              <svg className="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fillRule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clipRule="evenodd"
                />
              </svg>
              {governance.statusLabel}
            </div>
            <p className="text-amber-200/90 leading-relaxed">
              This document reflects verified static codebase analysis and documented infrastructure
              for Orchestra. It must be formally reviewed and approved by the platform owner or legal
              counsel before official publication. Automatic publication via environment variables alone
              is strictly prohibited.
            </p>
          </div>
        )}

        {/* Cookie Table */}
        <Card>
          <h2 className="text-base sm:text-lg font-bold text-[#F8F8FC] mb-3 border-b border-white/[0.08] pb-2">
            1. First-Party Cookies Deployed by Orchestra
          </h2>
          <p className="text-xs sm:text-sm text-[#A4A6B8] mb-4 leading-relaxed">
            Orchestra sets only strictly necessary first-party cookies required for secure user
            authentication, session continuity, and Cross-Site Request Forgery (CSRF) mitigation.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-[#A4A6B8] border-collapse">
              <thead>
                <tr className="border-b border-white/[0.08] text-[#F8F8FC] uppercase tracking-wider font-mono text-[11px]">
                  <th className="py-2.5 px-3">Cookie Name</th>
                  <th className="py-2.5 px-3">Type &amp; Security</th>
                  <th className="py-2.5 px-3">Lifespan</th>
                  <th className="py-2.5 px-3">Purpose</th>
                  <th className="py-2.5 px-3">Category</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                <tr>
                  <td className="py-3 px-3 font-mono text-[#8B7CFF] font-semibold">access_token</td>
                  <td className="py-3 px-3">HttpOnly, SameSite=Lax</td>
                  <td className="py-3 px-3">15 Minutes</td>
                  <td className="py-3 px-3">Authenticates API requests using signed JWT</td>
                  <td className="py-3 px-3">
                    <span className="inline-block px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      Essential
                    </span>
                  </td>
                </tr>
                <tr>
                  <td className="py-3 px-3 font-mono text-[#8B7CFF] font-semibold">refresh_token</td>
                  <td className="py-3 px-3">HttpOnly, SameSite=Lax</td>
                  <td className="py-3 px-3">7 Days</td>
                  <td className="py-3 px-3">Enables single-flight session rotation without credential re-entry</td>
                  <td className="py-3 px-3">
                    <span className="inline-block px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      Essential
                    </span>
                  </td>
                </tr>
                <tr>
                  <td className="py-3 px-3 font-mono text-[#8B7CFF] font-semibold">csrf_token</td>
                  <td className="py-3 px-3">Non-HttpOnly, SameSite=Lax</td>
                  <td className="py-3 px-3">Session</td>
                  <td className="py-3 px-3">Cryptographic token bound to session for CSRF defense on mutating requests</td>
                  <td className="py-3 px-3">
                    <span className="inline-block px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      Essential
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>

        {/* Local Storage Inventory */}
        <Card>
          <h2 className="text-base sm:text-lg font-bold text-[#F8F8FC] mb-3 border-b border-white/[0.08] pb-2">
            2. Browser Local Storage Utilization
          </h2>
          <div className="space-y-4 text-xs sm:text-sm text-[#A4A6B8]">
            <p className="leading-relaxed">
              Orchestra uses HTML5 Local Storage solely for client-side state preservation. No tokens,
              passwords, or secrets are ever persisted to Local Storage.
            </p>

            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-[#15151B] border border-white/[0.06] space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[#F8F8FC] font-semibold">orchestra_selected_project_id</span>
                  <span className="text-[10px] font-mono uppercase bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/30">
                    Functional
                  </span>
                </div>
                <p className="text-xs text-[#929292]">
                  Stores the integer identifier of your active project to ensure seamless workspace
                  continuity across page refreshes.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-[#15151B] border border-white/[0.06] space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[#F8F8FC] font-semibold">orchestra_cookie_consent_v1</span>
                  <span className="text-[10px] font-mono uppercase bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/30">
                    Functional
                  </span>
                </div>
                <p className="text-xs text-[#929292]">
                  Stores a structured JSON record containing your privacy preferences and timestamp to
                  prevent the consent banner from re-appearing on every visit.
                </p>
              </div>
            </div>
          </div>
        </Card>

        {/* Third-Party Disclosure */}
        <Card>
          <h2 className="text-base sm:text-lg font-bold text-[#F8F8FC] mb-3 border-b border-white/[0.08] pb-2">
            3. Third-Party Trackers &amp; Advertising
          </h2>
          <p className="text-xs sm:text-sm text-[#A4A6B8] leading-relaxed">
            Orchestra deploys <strong className="text-[#F8F8FC]">zero third-party advertising cookies, social media tracking pixels, or cross-site tracking scripts</strong>.
            Your interaction with Orchestra is never shared with behavioral data brokers or advertising syndicates.
          </p>
        </Card>
      </div>
    </div>
  );
}
