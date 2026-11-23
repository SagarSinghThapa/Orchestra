"use client";

import React, { useSyncExternalStore } from "react";
import Link from "next/link";
import { usePrivacy } from "./PrivacyContext";

function subscribe(): () => void {
  return () => {};
}
function getClientSnapshot(): boolean {
  return true;
}
function getServerSnapshot(): boolean {
  return false;
}

export function CookieConsentBanner() {
  const { hasResponded, acknowledgeEssential, openPreferences } = usePrivacy();
  const isHydrated = useSyncExternalStore(
    subscribe,
    getClientSnapshot,
    getServerSnapshot
  );

  // Do not render during SSR or if consent has already been recorded
  if (!isHydrated || hasResponded) {
    return null;
  }

  return (
    <aside
      aria-label="Cookie and Privacy Consent"
      role="region"
      className="fixed bottom-4 right-4 left-4 sm:left-auto sm:right-6 sm:max-w-xl z-40 p-4 sm:p-5 bg-[#101014]/95 backdrop-blur-md border border-white/[0.12] rounded-xl shadow-2xl transition-all duration-300 ease-in-out"
    >
      <div className="flex flex-col gap-3 sm:gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full bg-emerald-400"
              aria-hidden="true"
            />
            <h2 className="text-sm sm:text-base font-semibold text-[#F8F8FC] tracking-tight">
              Privacy &amp; Cookie Notice
            </h2>
          </div>
          <p className="text-xs sm:text-sm text-[#A4A6B8] leading-relaxed">
            Orchestra uses strictly necessary cookies and local storage to authenticate
            your session, preserve your active workspace, and defend against CSRF attacks.
            No third-party advertising or optional tracking scripts are currently deployed.
            Review our{" "}
            <Link
              href="/privacy"
              className="text-[#8B7CFF] hover:text-[#A599FF] underline underline-offset-2 transition-colors focus:outline-none focus:ring-1 focus:ring-[#5146FF] rounded"
            >
              Privacy Policy
            </Link>{" "}
            and{" "}
            <Link
              href="/cookies"
              className="text-[#8B7CFF] hover:text-[#A599FF] underline underline-offset-2 transition-colors focus:outline-none focus:ring-1 focus:ring-[#5146FF] rounded"
            >
              Cookie Policy
            </Link>{" "}
            for full technical details.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5 sm:gap-3 w-full sm:w-auto">
          <button
            type="button"
            onClick={acknowledgeEssential}
            className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-lg bg-[#5146FF] hover:bg-[#4338CA] text-white shadow-md transition-colors focus:outline-none focus:ring-2 focus:ring-[#5146FF] focus:ring-offset-2 focus:ring-offset-[#101014]"
          >
            Acknowledge &amp; Continue
          </button>
          <button
            type="button"
            onClick={openPreferences}
            className="flex-1 sm:flex-none px-4 py-2 text-xs sm:text-sm font-medium rounded-lg bg-[#20212B] hover:bg-[#2A2B38] text-[#F8F8FC] border border-white/[0.12] transition-colors focus:outline-none focus:ring-2 focus:ring-white/20"
          >
            Customize Preferences
          </button>
        </div>
      </div>
    </aside>
  );
}
