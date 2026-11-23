"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { usePrivacy } from "./PrivacyContext";

function CookiePreferencesDialogContent() {
  const { closePreferences, consent, savePreferences } = usePrivacy();
  const [analyticsEnabled, setAnalyticsEnabled] = useState(() =>
    Boolean(consent?.categories?.analytics)
  );
  const modalRef = useRef<HTMLDivElement>(null);

  // Focus trap & focus restoration on unmount
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    if (modalRef.current) {
      const btn = modalRef.current.querySelector<HTMLElement>("button");
      btn?.focus();
    }
    return () => {
      prev?.focus();
    };
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closePreferences();
        return;
      }

      if (e.key === "Tab" && modalRef.current) {
        const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    },
    [closePreferences]
  );

  const handleSave = () => {
    savePreferences(analyticsEnabled);
  };

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm transition-opacity"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          closePreferences();
        }
      }}
    >
      <div
        ref={modalRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="privacy-modal-title"
        onKeyDown={handleKeyDown}
        className="w-full max-w-2xl bg-[#1A1A22] border border-white/[0.12] rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] text-[#F5F5F5]"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.08] bg-[#20212B]">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-[#5146FF]" aria-hidden="true" />
            <h2
              id="privacy-modal-title"
              className="text-base sm:text-lg font-bold text-[#F8F8FC] tracking-tight"
            >
              Privacy &amp; Cookie Preferences
            </h2>
          </div>
          <button
            type="button"
            onClick={closePreferences}
            aria-label="Close preferences"
            className="p-1.5 rounded-lg text-[#929292] hover:text-white hover:bg-white/[0.06] transition"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              viewBox="0 0 24 24"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="p-6 overflow-y-auto space-y-6 text-xs sm:text-sm">
          <p className="text-[#A4A6B8] leading-relaxed">
            Orchestra values transparency and user sovereignty over data. Review how
            storage technologies are utilized across the platform below.
          </p>

          {/* Category 1: Essential */}
          <div className="p-4 rounded-xl bg-[#20212B] border border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-[#F8F8FC]">
                    Strictly Necessary Cookies &amp; Storage
                  </h3>
                  <span className="inline-block px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                    Always Active
                  </span>
                </div>
                <p className="text-xs text-[#929292]">
                  Mandatory for core platform authentication, session state, and CSRF protection.
                </p>
              </div>

              {/* Disabled switch */}
              <div className="relative inline-flex items-center shrink-0">
                <input
                  type="checkbox"
                  checked={true}
                  disabled={true}
                  aria-disabled="true"
                  aria-label="Strictly Necessary Cookies are always active"
                  className="sr-only"
                />
                <div className="w-10 h-5 bg-[#5146FF] rounded-full opacity-60 cursor-not-allowed">
                  <div className="w-4 h-4 bg-white rounded-full transform translate-x-5 translate-y-0.5" />
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-white/[0.04] space-y-1.5 text-xs text-[#A4A6B8]">
              <div className="flex justify-between py-1 border-b border-white/[0.03]">
                <span className="font-mono text-[#F8F8FC]">access_token</span>
                <span>HttpOnly Cookie · 15 mins (API Auth)</span>
              </div>
              <div className="flex justify-between py-1 border-b border-white/[0.03]">
                <span className="font-mono text-[#F8F8FC]">refresh_token</span>
                <span>HttpOnly Cookie · 7 days (Session Rotation)</span>
              </div>
              <div className="flex justify-between py-1 border-b border-white/[0.03]">
                <span className="font-mono text-[#F8F8FC]">csrf_token</span>
                <span>SameSite Cookie · Session (CSRF Defense)</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="font-mono text-[#F8F8FC]">orchestra_selected_project_id</span>
                <span>LocalStorage · Workspace Persistence</span>
              </div>
            </div>
          </div>

          {/* Category 2: Optional Analytics */}
          <div className="p-4 rounded-xl bg-[#20212B] border border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-[#F8F8FC]">
                    Optional Analytics &amp; Diagnostics
                  </h3>
                  <span className="inline-block px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-white/[0.06] text-[#A4A6B8] border border-white/[0.12]">
                    Not Currently Available
                  </span>
                </div>
                <p className="text-xs text-[#929292]">
                  Future client-side performance and error diagnostics. Off by default.
                </p>
              </div>

              {/* Interactive switch */}
              <button
                type="button"
                role="switch"
                aria-checked={analyticsEnabled}
                onClick={() => setAnalyticsEnabled(!analyticsEnabled)}
                aria-label="Toggle Optional Analytics"
                className={`relative inline-flex items-center h-5 w-10 shrink-0 cursor-pointer rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-[#5146FF] focus:ring-offset-2 focus:ring-offset-[#20212B] ${
                  analyticsEnabled ? "bg-[#5146FF]" : "bg-white/[0.16]"
                }`}
              >
                <span
                  className={`inline-block w-4 h-4 transform rounded-full bg-white transition duration-200 ease-in-out ${
                    analyticsEnabled ? "translate-x-5" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>

            <p className="text-xs text-[#A4A6B8] leading-relaxed">
              Orchestra does not currently deploy third-party analytics trackers, advertising
              cookies, or behavioral profiling tools. This preference pre-sets your choice should
              diagnostic telemetry be introduced in future platform releases.
            </p>

            <div className="p-2.5 rounded-lg bg-black/30 border border-white/[0.04] text-[11px] text-[#A4A6B8] leading-relaxed">
              <span className="font-semibold text-[#F8F8FC] block mb-0.5">
                Server-Side Observability Disclosure:
              </span>
              Standard server-side API request counts, latencies, and operator-configured LangSmith
              pipeline traces operate on the backend infrastructure for platform reliability.
              They are not driven by browser tracking cookies.
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/[0.08] bg-[#20212B]">
          <button
            type="button"
            onClick={closePreferences}
            className="px-4 py-2 text-xs sm:text-sm font-medium rounded-lg text-[#F8F8FC] hover:bg-white/[0.06] transition focus:outline-none focus:ring-2 focus:ring-white/20"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            className="px-5 py-2 text-xs sm:text-sm font-medium rounded-lg bg-[#5146FF] hover:bg-[#4338CA] text-white shadow-md transition focus:outline-none focus:ring-2 focus:ring-[#5146FF] focus:ring-offset-2 focus:ring-offset-[#20212B]"
          >
            Save Preferences
          </button>
        </div>
      </div>
    </div>
  );
}

export function CookiePreferencesModal() {
  const { isPreferencesOpen } = usePrivacy();

  if (!isPreferencesOpen) {
    return null;
  }

  return <CookiePreferencesDialogContent />;
}
