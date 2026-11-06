import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, ApiError, setAuthFailureHandler } from "@/services/apiClient";

describe("ApiClient & ApiAdapter Security & Transport", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("enforces credentials: 'include' on all outbound HTTP requests", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ success: true }),
    });
    global.fetch = mockFetch;

    await api.get("/projects");

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/projects");
    expect(options.credentials).toBe("include");
  });

  it("attaches X-Orchestra-Request: 'true' custom header to all requests", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 1 }),
    });
    global.fetch = mockFetch;

    await api.post("/projects", { name: "Test Project" });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [, options] = mockFetch.mock.calls[0];
    expect(options.headers["X-Orchestra-Request"]).toBe("true");
    expect(options.headers["Content-Type"]).toBe("application/json");
  });

  it("handles HTTP 204 No Content without invoking response.json()", async () => {
    const jsonSpy = vi.fn();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: jsonSpy,
    });
    global.fetch = mockFetch;

    const result = await api.delete("/projects/123");

    expect(result).toBeNull();
    expect(jsonSpy).not.toHaveBeenCalled();
  });

  it("normalizes HTTP errors into ApiError instances with message and status", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: "Viewer role is not authorized to modify files" }),
    });
    global.fetch = mockFetch;

    await expect(api.post("/projects/1/developer", {})).rejects.toThrow(ApiError);
    try {
      await api.post("/projects/1/developer", {});
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(403);
      expect(apiErr.message).toBe("Viewer role is not authorized to modify files");
    }
  });

  it("coalesces concurrent 401s into a single POST /auth/refresh call", async () => {
    let refreshCalls = 0;
    const mockFetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.endsWith("/auth/refresh")) {
        refreshCalls++;
        return {
          ok: true,
          status: 200,
          json: async () => ({ message: "refreshed" }),
        };
      }
      // First attempt fails with 401, retried attempt succeeds with 200
      if (!mockFetch.mock.calls.some(([u]) => u.endsWith("/auth/refresh"))) {
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Token expired" }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ data: "success" }),
      };
    });
    global.fetch = mockFetch;

    // Trigger two concurrent requests that both receive 401
    const [res1, res2] = await Promise.all([
      api.get("/resource-1"),
      api.get("/resource-2"),
    ]);

    expect(res1).toEqual({ data: "success" });
    expect(res2).toEqual({ data: "success" });
    expect(refreshCalls).toBe(1); // Single-flight mutex guarantee
  });

  it("triggers onAuthFailure when token refresh fails with 401", async () => {
    const failureHandler = vi.fn();
    setAuthFailureHandler(failureHandler);

    const mockFetch = vi.fn().mockImplementation(async (url: string) => {
      if (url.endsWith("/auth/refresh")) {
        return {
          ok: false,
          status: 401,
          json: async () => ({ detail: "Refresh token expired" }),
        };
      }
      return {
        ok: false,
        status: 401,
        json: async () => ({ detail: "Unauthorized" }),
      };
    });
    global.fetch = mockFetch;

    await expect(api.get("/protected")).rejects.toThrow(ApiError);
    expect(failureHandler).toHaveBeenCalled();
  });

  it("never reads or writes tokens in localStorage", async () => {
    const getItemSpy = vi.spyOn(Storage.prototype, "getItem");
    const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });
    global.fetch = mockFetch;

    await api.get("/test");

    expect(getItemSpy).not.toHaveBeenCalledWith("jwt_token");
    expect(getItemSpy).not.toHaveBeenCalledWith("token");
    expect(setItemSpy).not.toHaveBeenCalledWith("jwt_token", expect.anything());
  });

  it("captures X-Request-ID on API errors as requestId", async () => {
    const mockHeaders = new Headers();
    mockHeaders.set("X-Request-ID", "req_test_12345");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      headers: mockHeaders,
      json: async () => ({ detail: "Internal server error" }),
    });
    global.fetch = mockFetch;

    try {
      await api.get("/projects");
      expect.fail("Expected api.get to throw ApiError");
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(500);
      expect(apiErr.requestId).toBe("req_test_12345");
    }
  });

  it("handles HTTP 429 Too Many Requests by parsing Retry-After and does not auto-retry", async () => {
    const mockHeaders = new Headers();
    mockHeaders.set("Retry-After", "42");
    mockHeaders.set("X-Request-ID", "req_rate_limit_001");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: mockHeaders,
      json: async () => ({ detail: "Too many requests. Please try again in 42 seconds." }),
    });
    global.fetch = mockFetch;

    try {
      await api.post("/projects/1/research", { query: "AI architecture" });
      expect.fail("Expected api.post to throw ApiError on 429");
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(429);
      expect(apiErr.retryAfter).toBe(42);
      expect(apiErr.requestId).toBe("req_rate_limit_001");
      expect(apiErr.message).toContain("42 seconds");
      // Must NOT retry mutating request
      expect(mockFetch).toHaveBeenCalledTimes(1);
    }
  });

  it("handles HTTP 429 with fallback message when Retry-After is absent", async () => {
    const mockHeaders = new Headers();
    mockHeaders.set("X-Request-ID", "req_fallback_429");
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      headers: mockHeaders,
      json: async () => ({}),
    });
    global.fetch = mockFetch;

    try {
      await api.get("/auth/login");
      expect.fail("Expected api.get to throw ApiError on 429");
    } catch (err: unknown) {
      const apiErr = err as ApiError;
      expect(apiErr.status).toBe(429);
      expect(apiErr.retryAfter).toBeUndefined();
      expect(apiErr.message).toBe("Too many requests. Please wait a moment and try again.");
    }
  });

  describe("Same-Origin API Routing & Base URL Contract", () => {
    beforeEach(() => {
      vi.unstubAllEnvs();
    });

    afterEach(() => {
      vi.unstubAllEnvs();
    });

    it("respects explicit absolute development API base URL", async () => {
      vi.stubEnv("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8001");
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ id: 1, email: "user@example.com" }),
      });
      global.fetch = mockFetch;

      await api.get("/auth/me");

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe("http://127.0.0.1:8001/auth/me");
      expect(options.credentials).toBe("include");
    });

    it("generates relative same-origin URLs in production mode when NEXT_PUBLIC_API_URL is empty", async () => {
      vi.stubEnv("NODE_ENV", "production");
      vi.stubEnv("NEXT_PUBLIC_API_URL", "");
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ id: 1, email: "user@example.com" }),
      });
      global.fetch = mockFetch;

      await api.get("/auth/me");

      expect(mockFetch).toHaveBeenCalledTimes(1);
      const [url, options] = mockFetch.mock.calls[0];
      expect(url).toBe("/auth/me");
      expect(options.credentials).toBe("include");
    });

    it("routes authentication endpoints through same origin without hardcoding hostname", async () => {
      vi.stubEnv("NODE_ENV", "production");
      vi.stubEnv("NEXT_PUBLIC_API_URL", "");
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ message: "authenticated" }),
      });
      global.fetch = mockFetch;

      await api.post("/auth/login", { email: "test@example.com", password: "Password123!" });
      await api.post("/auth/register", { email: "new@example.com", password: "Password123!" });
      await api.post("/auth/logout");

      expect(mockFetch).toHaveBeenCalledTimes(3);
      expect(mockFetch.mock.calls[0][0]).toBe("/auth/login");
      expect(mockFetch.mock.calls[1][0]).toBe("/auth/register");
      expect(mockFetch.mock.calls[2][0]).toBe("/auth/logout");
      // Verify credentials & CSRF header preserved
      for (const call of mockFetch.mock.calls) {
        expect(call[1].credentials).toBe("include");
        expect(call[1].headers["X-Orchestra-Request"]).toBe("true");
      }
    });

    it("routes project, document, chat, developer, and evaluation calls through same-origin relative paths", async () => {
      vi.stubEnv("NODE_ENV", "production");
      vi.stubEnv("NEXT_PUBLIC_API_URL", "");
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ success: true }),
      });
      global.fetch = mockFetch;

      await api.get("/projects");
      await api.get("/projects/10/documents");
      await api.post("/projects/10/orchestrate", { query: "Research inquiry" });
      await api.post("/projects/10/developer", { query: "Code modification" });
      await api.get("/evaluations/benchmarks");

      expect(mockFetch).toHaveBeenCalledTimes(5);
      expect(mockFetch.mock.calls[0][0]).toBe("/projects");
      expect(mockFetch.mock.calls[1][0]).toBe("/projects/10/documents");
      expect(mockFetch.mock.calls[2][0]).toBe("/projects/10/orchestrate");
      expect(mockFetch.mock.calls[3][0]).toBe("/projects/10/developer");
      expect(mockFetch.mock.calls[4][0]).toBe("/evaluations/benchmarks");
    });

    it("executes single-flight token refresh against relative same-origin /auth/refresh", async () => {
      vi.stubEnv("NODE_ENV", "production");
      vi.stubEnv("NEXT_PUBLIC_API_URL", "");

      let refreshUrlCalled: string | null = null;
      const mockFetch = vi.fn().mockImplementation(async (url: string) => {
        if (url === "/auth/refresh") {
          refreshUrlCalled = url;
          return {
            ok: true,
            status: 200,
            json: async () => ({ message: "refreshed" }),
          };
        }
        if (!refreshUrlCalled) {
          return {
            ok: false,
            status: 401,
            json: async () => ({ detail: "Token expired" }),
          };
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({ data: "success" }),
        };
      });
      global.fetch = mockFetch;

      const result = await api.get("/projects");

      expect(refreshUrlCalled).toBe("/auth/refresh");
      expect(result).toEqual({ data: "success" });
    });
  });
});

