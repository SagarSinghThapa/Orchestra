export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type AuthFailureHandler = () => void;
let onAuthFailure: AuthFailureHandler | null = null;

export function setAuthFailureHandler(handler: AuthFailureHandler | null) {
  onAuthFailure = handler;
}

export function getBaseUrl(): string {
  const rawUrl = process.env.NEXT_PUBLIC_API_URL;
  if (rawUrl) {
    if (!rawUrl.startsWith("http://") && !rawUrl.startsWith("https://")) {
      throw new Error("Invalid NEXT_PUBLIC_API_URL: must start with http:// or https://");
    }
    return rawUrl.replace(/\/+$/, "");
  }
  if (process.env.NODE_ENV === "production") {
    throw new Error("NEXT_PUBLIC_API_URL must be defined in production environment");
  }
  return "http://localhost:8000";
}

let refreshPromise: Promise<void> | null = null;

class ApiAdapter {
  async request<T = unknown>(
    endpoint: string,
    options: RequestInit = {},
    isRetry = false
  ): Promise<T> {
    const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;

    const headers: Record<string, string> = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      "X-Orchestra-Request": "true",
      ...((options.headers as Record<string, string>) || {}),
    };

    // Temporary mock fallback for unmigrated endpoints while in mock mode (Wave 10.5 removes this)
    if (process.env.NEXT_PUBLIC_USE_MOCK_API === "true" && (endpoint === "/developer/task" || endpoint === "/evaluations/summary")) {
      return this._handleMock(endpoint, options) as Promise<T>;
    }

    const baseUrl = getBaseUrl();
    const url = endpoint.startsWith("http") ? endpoint : `${baseUrl}${endpoint}`;

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        credentials: "include",
      });

      // Handle 401 Unauthorized with single-flight refresh queue
      if (response.status === 401 && !isRetry && !this._isAuthRoute(endpoint)) {
        if (!refreshPromise) {
          refreshPromise = (async () => {
            try {
              const refreshResp = await fetch(`${baseUrl}/auth/refresh`, {
                method: "POST",
                credentials: "include",
                headers: {
                  "Content-Type": "application/json",
                  "X-Orchestra-Request": "true",
                },
              });
              if (!refreshResp.ok) {
                if (onAuthFailure) onAuthFailure();
                throw new ApiError(refreshResp.status, "Session expired. Please log in again.");
              }
            } catch (err) {
              if (onAuthFailure) onAuthFailure();
              throw err;
            } finally {
              refreshPromise = null;
            }
          })();
        }

        try {
          await refreshPromise;
          // Retry original request once
          return await this.request<T>(endpoint, options, true);
        } catch {
          throw new ApiError(401, "Session expired. Please log in again.");
        }
      }

      if (!response.ok) {
        let errorData: Record<string, unknown> | null = null;
        try {
          errorData = await response.json();
        } catch {
          // Response body was not JSON
        }

        const message =
          (typeof errorData?.detail === "string" ? errorData.detail : null) ||
          (typeof errorData?.message === "string" ? errorData.message : null) ||
          `API Error (${response.status}): ${response.statusText}`;

        throw new ApiError(response.status, message, errorData?.detail || errorData);
      }

      // Handle 204 No Content or empty responses cleanly
      if (response.status === 204 || response.headers.get("content-length") === "0") {
        return null as unknown as T;
      }

      return (await response.json()) as T;
    } catch (error) {
      if (error instanceof ApiError) {
        throw error;
      }
      throw new ApiError(
        0,
        "Orchestra backend unreachable. Please verify server connectivity.",
        error
      );
    }
  }

  private _isAuthRoute(endpoint: string): boolean {
    return (
      endpoint === "/auth/login" ||
      endpoint === "/auth/register" ||
      endpoint === "/auth/refresh" ||
      endpoint.endsWith("/auth/login") ||
      endpoint.endsWith("/auth/register") ||
      endpoint.endsWith("/auth/refresh")
    );
  }

  get<T = unknown>(endpoint: string, options: RequestInit = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "GET" });
  }

  post<T = unknown>(endpoint: string, data?: unknown, options: RequestInit = {}): Promise<T> {
    const isFormData = typeof FormData !== "undefined" && data instanceof FormData;
    return this.request<T>(endpoint, {
      ...options,
      method: "POST",
      body: isFormData ? (data as FormData) : JSON.stringify(data),
    });
  }

  delete<T = unknown>(endpoint: string, options: RequestInit = {}): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "DELETE" });
  }

  // Temporary mock handler retained only for unmigrated endpoints (Wave 10.5 decommissions this completely)
  private async _handleMock(endpoint: string, options: RequestInit): Promise<unknown> {
    await new Promise((resolve) => setTimeout(resolve, 500));
    if (endpoint === "/developer/task" && options.body) {
      const body = JSON.parse(options.body as string);
      return {
        output_payload: {
          status: "success",
          artifacts: [],
          result: {
            summary: `Mock result for ${body.task_type}`,
            plan: ["Inspect workspace", "Synthesize code", "Validate AST"],
            files_changed: [],
            diffs: {},
            validation: {},
            warnings: [],
          },
        },
        trace_id: `trace-mock-${Date.now()}`,
      };
    }
    if (endpoint === "/evaluations/summary") {
      return {
        total_runs: 0,
        passed: 0,
        failed: 0,
        running: 0,
        pending: 0,
        metrics: [],
        agents: [],
        benchmarks: [],
        recent_runs: [],
      };
    }
    return { success: true, mocked: true };
  }
}

export const api = new ApiAdapter();
