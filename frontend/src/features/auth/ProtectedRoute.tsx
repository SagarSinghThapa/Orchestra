"use client";

import React, { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "./AuthContext";
import { LoadingState } from "@/components/ui/StateWrappers";

export function sanitizeRedirectUrl(url: string | null): string {
  if (!url) return "/dashboard";
  // Must be an internal relative path starting with a single '/'
  if (url.startsWith("/") && !url.startsWith("//") && !url.includes("://")) {
    return url;
  }
  return "/dashboard";
}

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      const sanitized = sanitizeRedirectUrl(pathname);
      router.replace(`/login?redirect=${encodeURIComponent(sanitized)}`);
    }
  }, [status, pathname, router]);

  if (status === "loading") {
    return (
      <div className="flex h-full w-full items-center justify-center p-12">
        <LoadingState message="Verifying session..." />
      </div>
    );
  }

  if (status === "unauthenticated") {
    return null;
  }

  return <>{children}</>;
}
