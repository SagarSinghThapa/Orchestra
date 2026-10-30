import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, act } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/features/auth/AuthContext";
import { sanitizeRedirectUrl } from "@/features/auth/ProtectedRoute";

function TestConsumer() {
  const { user, status, logout } = useAuth();
  return (
    <div>
      <div data-testid="status">{status}</div>
      <div data-testid="user">{user?.email || "no-user"}</div>
      <button onClick={logout} data-testid="logout-btn">
        Logout
      </button>
    </div>
  );
}

describe("Authentication & Route Protection Architecture", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("bootstraps session via GET /auth/me on initial render", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: 1,
        username: "lead_dev",
        email: "dev@orchestra.ai",
        role: "admin",
      }),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    // Initial state is loading while /auth/me bootstrap is in flight
    expect(screen.getByTestId("status")).toHaveTextContent("loading");

    // Wait for bootstrap effect
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(screen.getByTestId("status")).toHaveTextContent("authenticated");
    expect(screen.getByTestId("user")).toHaveTextContent("dev@orchestra.ai");
  });

  it("handles unauthenticated initial state when /auth/me returns 401", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Not authenticated" }),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    expect(screen.getByTestId("status")).toHaveTextContent("loading");

    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(screen.getByTestId("status")).toHaveTextContent("unauthenticated");
    expect(screen.getByTestId("user")).toHaveTextContent("no-user");
  });

  it("sanitizes redirect URLs preventing open-redirect attacks", () => {
    expect(sanitizeRedirectUrl("/dashboard")).toBe("/dashboard");
    expect(sanitizeRedirectUrl("/chat?query=hello")).toBe("/chat?query=hello");

    // External URLs must be rejected and defaulted to /dashboard
    expect(sanitizeRedirectUrl("https://evil.com/phishing")).toBe("/dashboard");
    expect(sanitizeRedirectUrl("//attacker.com")).toBe("/dashboard");
    expect(sanitizeRedirectUrl("javascript:alert(1)")).toBe("/dashboard");
    expect(sanitizeRedirectUrl("")).toBe("/dashboard");
    expect(sanitizeRedirectUrl(null)).toBe("/dashboard");
  });
});
