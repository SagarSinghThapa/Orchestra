"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/features/auth/AuthContext";
import { getStoredConsent, saveStoredConsent } from "@/features/privacy";
import { sanitizeRedirectUrl } from "@/features/auth/ProtectedRoute";
import { ApiError } from "@/services/apiClient";

function LoginForm() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isRateLimited, setIsRateLimited] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const { login, register } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      setError("Please fill in all fields.");
      setIsRateLimited(false);
      return;
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      setIsRateLimited(false);
      return;
    }

    setError("");
    setIsRateLimited(false);
    setSubmitting(true);

    try {
      const cleanEmail = email.trim().toLowerCase();
      if (mode === "login") {
        await login(cleanEmail, password);
      } else {
        await register(cleanEmail, password);
      }
      if (!getStoredConsent()) {
        saveStoredConsent(false);
      }
      const redirect = sanitizeRedirectUrl(searchParams.get("redirect"));
      router.push(redirect);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 429) {
        setIsRateLimited(true);
        setError(err.message || "Too many attempts. Please wait a moment and try again.");
      } else {
        setIsRateLimited(false);
        const errorMsg =
          err instanceof Error ? err.message : "Authentication failed. Please check your credentials.";
        setError(errorMsg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-[#101014] workspace-gradient-bg px-4 py-8">
      <Card className="w-full max-w-md p-6 sm:p-8 space-y-6 bg-[#20212B] border border-white/[0.08] shadow-2xl rounded-2xl text-[#F5F5F5]">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-[#5146FF] to-[#8B7CFF] text-white shadow-lg shadow-indigo-500/20 mb-3">
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 10V3L4 14h7v7l9-11h-7z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[#F8F8FC]">
            {mode === "login" ? "Sign in to Orchestra" : "Create an account"}
          </h1>
          <p className="mt-2 text-sm text-[#A4A6B8]">
            Multi-Agent AI Engineering & Research Platform
          </p>
        </div>

        {/* Mode Selector */}
        <div className="flex rounded-xl bg-[#15151B] p-1 border border-white/[0.08]">
          <button
            type="button"
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition-all ${
              mode === "login"
                ? "bg-[#5146FF] text-white shadow-sm font-semibold"
                : "text-[#A4A6B8] hover:text-white"
            }`}
            onClick={() => {
              setMode("login");
              setError("");
              setIsRateLimited(false);
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition-all ${
              mode === "register"
                ? "bg-[#5146FF] text-white shadow-sm font-semibold"
                : "text-[#A4A6B8] hover:text-white"
            }`}
            onClick={() => {
              setMode("register");
              setError("");
              setIsRateLimited(false);
            }}
          >
            Create Account
          </button>
        </div>

        {error && (
          <div
            role="alert"
            className={`rounded-lg p-3 text-sm border transition-all ${
              isRateLimited
                ? "bg-amber-950/40 text-amber-200 border-amber-600/50"
                : "bg-red-950/40 text-red-200 border-red-600/50"
            }`}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[#E0E2EC] mb-1.5">
              Email Address
            </label>
            <input
              type="email"
              required
              disabled={submitting}
              className="w-full rounded-lg bg-[#15151B] border border-white/[0.12] px-3.5 py-2.5 text-white placeholder-[#717384] focus:outline-none focus:border-[#5146FF] focus:ring-1 focus:ring-[#5146FF] transition-all disabled:opacity-50 disabled:bg-[#15151B]/50"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@domain.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#E0E2EC] mb-1.5">
              Password
            </label>
            <input
              type="password"
              required
              disabled={submitting}
              className="w-full rounded-lg bg-[#15151B] border border-white/[0.12] px-3.5 py-2.5 text-white placeholder-[#717384] focus:outline-none focus:border-[#5146FF] focus:ring-1 focus:ring-[#5146FF] transition-all disabled:opacity-50 disabled:bg-[#15151B]/50"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters..."
            />
          </div>

          <Button
            type="submit"
            className="w-full justify-center py-2.5 bg-[#5146FF] hover:bg-[#4338CA] text-white font-medium rounded-lg shadow-lg shadow-indigo-500/25 transition-all focus:outline-none focus:ring-2 focus:ring-[#5146FF] focus:ring-offset-2 focus:ring-offset-[#20212B] disabled:opacity-50"
            disabled={submitting}
          >
            {submitting ? "Please wait..." : mode === "login" ? "Sign In" : "Register"}
          </Button>
        </form>

        <div className="pt-4 border-t border-white/[0.06] flex items-center justify-center gap-3 text-xs text-[#929292]">
          <Link href="/privacy" className="hover:text-white transition">
            Privacy Policy
          </Link>
          <span>·</span>
          <Link href="/cookies" className="hover:text-white transition">
            Cookie Policy
          </Link>
        </div>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#101014] text-[#A4A6B8]">
          <p className="text-[#A4A6B8]">Loading authentication...</p>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
