import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { AuthProvider, useAuth } from "@/features/auth/AuthContext";
import { sanitizeRedirectUrl } from "@/features/auth/ProtectedRoute";
import LoginPage from "@/app/login/page";
import { api, ApiError } from "@/services/apiClient";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
  }),
  useSearchParams: () => ({
    get: vi.fn().mockReturnValue(null),
  }),
}));

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

  it("cleans up selected project id from localStorage on logout", async () => {
    localStorage.setItem("orchestra_selected_project_id", "42");
    expect(localStorage.getItem("orchestra_selected_project_id")).toBe("42");

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: "Logged out" }),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>
    );

    const logoutBtn = screen.getByTestId("logout-btn");
    await act(async () => {
      fireEvent.click(logoutBtn);
    });

    expect(localStorage.getItem("orchestra_selected_project_id")).toBeNull();
  });

  it("submits sanitized lowercase and trimmed email on login", async () => {
    let capturedBody: any = null;
    global.fetch = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      if (url.includes("/auth/login")) {
        capturedBody = JSON.parse(init?.body as string);
        return {
          ok: true,
          status: 200,
          json: async () => ({ access_token: "tok", refresh_token: "ref" }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ id: 1, email: "sanitized_user@orchestra.ai" }),
      };
    });

    const { container } = render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    );

    const emailInput = screen.getByPlaceholderText("you@domain.com");
    const passwordInput = screen.getByPlaceholderText("At least 8 characters...");
    const submitBtn = container.querySelector('button[type="submit"]') as HTMLButtonElement;

    await act(async () => {
      fireEvent.change(emailInput, { target: { value: "  Sanitized_User@Orchestra.AI  " } });
      fireEvent.change(passwordInput, { target: { value: "Password123!" } });
    });

    await act(async () => {
      fireEvent.click(submitBtn);
    });

    expect(capturedBody).not.toBeNull();
    expect(capturedBody.email).toBe("sanitized_user@orchestra.ai");
  });

  it("displays rate-limit alert with guidance when backend returns 429", async () => {
    global.fetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.includes("/auth/login")) {
        return {
          ok: false,
          status: 429,
          headers: new Headers({ "retry-after": "30" }),
          json: async () => ({ detail: "Too many login attempts. Please wait 30 seconds." }),
        };
      }
      return {
        ok: false,
        status: 401,
        json: async () => ({ detail: "Unauthenticated" }),
      };
    });

    const { container } = render(
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    );

    const emailInput = screen.getByPlaceholderText("you@domain.com");
    const passwordInput = screen.getByPlaceholderText("At least 8 characters...");
    const submitBtn = container.querySelector('button[type="submit"]') as HTMLButtonElement;

    await act(async () => {
      fireEvent.change(emailInput, { target: { value: "ratelimited@orchestra.ai" } });
      fireEvent.change(passwordInput, { target: { value: "Password123!" } });
    });

    await act(async () => {
      fireEvent.click(submitBtn);
    });

    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(/Too many login attempts/i);
    expect(alert.className).toContain("bg-amber-50");
  });
});
