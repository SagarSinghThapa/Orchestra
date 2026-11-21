"use client";

import React, { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/features/auth/AuthContext";
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
    <div className="flex items-center justify-center min-h-screen bg-gray-50 px-4">
      <Card className="w-full max-w-md p-8 space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            {mode === "login" ? "Sign in to Orchestra" : "Create an account"}
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            Multi-Agent AI Engineering & Research Platform
          </p>
        </div>

        {/* Mode Selector */}
        <div className="flex rounded-md bg-gray-100 p-1 border">
          <button
            type="button"
            className={`flex-1 rounded py-1.5 text-sm font-medium transition-colors ${
              mode === "login"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-900"
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
            className={`flex-1 rounded py-1.5 text-sm font-medium transition-colors ${
              mode === "register"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-900"
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
            className={`rounded-md p-3 text-sm border ${
              isRateLimited
                ? "bg-amber-50 text-amber-800 border-amber-200"
                : "bg-red-50 text-red-700 border-red-200"
            }`}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Email Address</label>
            <input
              type="email"
              required
              disabled={submitting}
              className="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@domain.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Password</label>
            <input
              type="password"
              required
              disabled={submitting}
              className="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters..."
            />
          </div>

          <Button type="submit" className="w-full justify-center" disabled={submitting}>
            {submitting ? "Please wait..." : mode === "login" ? "Sign In" : "Register"}
          </Button>
        </form>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-gray-50">
          <p className="text-gray-500">Loading authentication...</p>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
