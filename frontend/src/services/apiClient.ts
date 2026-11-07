export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown,
    public retryAfter?: number,
    public requestId?: string
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
  // Playwright E2E testing environment override:
  if (typeof window !== "undefined" && window.location.port === "3001") {
    return "http://127.0.0.1:8001";
  }

  const rawUrl = process.env.NEXT_PUBLIC_API_URL;

  // If explicitly configured in environment:
  if (rawUrl !== undefined && rawUrl !== null) {
    const trimmed = rawUrl.trim();
    if (trimmed === "" || trimmed === "/" || trimmed.toLowerCase() === "same-origin") {
      return "";
    }
    if (!trimmed.startsWith("http://") && !trimmed.startsWith("https://")) {
      throw new Error(
        "Invalid NEXT_PUBLIC_API_URL: must start with http:// or https://, or be empty for same-origin"
      );
    }
    return trimmed.replace(/\/+$/, "");
  }

  // Deployed production default: same-origin relative URLs via reverse proxy
  if (process.env.NODE_ENV === "production") {
    return "";
  }

  // Standalone local development default (without reverse proxy)
  return "http://localhost:8000";
}

let refreshPromise: Promise<void> | null = null;
let lastRefreshTime = 0;

class ApiAdapter {
  async request<T = unknown>(
    endpoint: string,
    options: RequestInit = {},
    isRetry = false
  ): Promise<T> {
    const requestStartTime = Date.now();
    const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;

    const headers: Record<string, string> = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      "X-Orchestra-Request": "true",
      ...((options.headers as Record<string, string>) || {}),
    };

    const baseUrl = getBaseUrl();
    const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const url = endpoint.startsWith("http")
      ? endpoint
      : baseUrl
        ? `${baseUrl}${normalizedEndpoint}`
        : normalizedEndpoint;

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        credentials: "include",
      });

      // Handle 401 Unauthorized with single-flight refresh queue
      if (response.status === 401 && !isRetry && !this._isAuthRoute(endpoint)) {
        if (lastRefreshTime > requestStartTime) {
          return this.request<T>(endpoint, options, true);
        }

        if (!refreshPromise) {
          refreshPromise = (async () => {
            try {
              const refreshUrl = baseUrl ? `${baseUrl}/auth/refresh` : "/auth/refresh";
              const refreshResp = await fetch(refreshUrl, {
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
              lastRefreshTime = Date.now();
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

        const requestId = response.headers?.get ? response.headers.get("x-request-id") || undefined : undefined;

        if (response.status === 429) {
          const rawRetryAfter = response.headers?.get ? response.headers.get("retry-after") : null;
          const parsedRetry = rawRetryAfter ? parseInt(rawRetryAfter, 10) : NaN;
          const retryAfter = !isNaN(parsedRetry) && parsedRetry > 0 ? parsedRetry : undefined;

          const message =
            (typeof errorData?.detail === "string" ? errorData.detail : null) ||
            (retryAfter
              ? `Too many requests. Please try again in ${retryAfter} seconds.`
              : "Too many requests. Please wait a moment and try again.");

          throw new ApiError(429, message, errorData?.detail || errorData, retryAfter, requestId);
        }

        const message =
          (typeof errorData?.detail === "string" ? errorData.detail : null) ||
          (typeof errorData?.message === "string" ? errorData.message : null) ||
          `API Error (${response.status}): ${response.statusText}`;

        throw new ApiError(response.status, message, errorData?.detail || errorData, undefined, requestId);
      }

      // Handle 204 No Content or empty responses cleanly
      const contentLength = response.headers?.get ? response.headers.get("content-length") : null;
      if (response.status === 204 || contentLength === "0") {
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

  async stream(
    endpoint: string,
    payload: unknown,
    options?: {
      signal?: AbortSignal;
      onEvent?: (event: { event: string; data: unknown }) => void;
    }
  ): Promise<void> {
    const baseUrl = getBaseUrl();
    const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const url = endpoint.startsWith("http")
      ? endpoint
      : baseUrl
        ? `${baseUrl}${normalizedEndpoint}`
        : normalizedEndpoint;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Orchestra-Request": "true",
      Accept: "text/event-stream",
    };

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
      credentials: "include",
      signal: options?.signal,
    });

    if (!response.ok) {
      let errorData: Record<string, unknown> | null = null;
      try {
        errorData = await response.json();
      } catch {
        // Response body was not JSON
      }

      const requestId = response.headers?.get ? response.headers.get("x-request-id") || undefined : undefined;

      if (response.status === 429) {
        const rawRetryAfter = response.headers?.get ? response.headers.get("retry-after") : null;
        const parsedRetry = rawRetryAfter ? parseInt(rawRetryAfter, 10) : NaN;
        const retryAfter = !isNaN(parsedRetry) && parsedRetry > 0 ? parsedRetry : undefined;

        const message =
          (typeof errorData?.detail === "string" ? errorData.detail : null) ||
          (retryAfter
            ? `Too many requests. Please try again in ${retryAfter} seconds.`
            : "Too many requests. Please wait a moment and try again.");

        throw new ApiError(429, message, errorData?.detail || errorData, retryAfter, requestId);
      }

      const message =
        (typeof errorData?.detail === "string" ? errorData.detail : null) ||
        (typeof errorData?.message === "string" ? errorData.message : null) ||
        `Stream request failed with status ${response.status}`;

      throw new ApiError(response.status, message, errorData?.detail || errorData, undefined, requestId);
    }

    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await response.json();
      if (data?.session_id) {
        options?.onEvent?.({ event: "session", data: { session_id: data.session_id } });
      }
      if (data?.intent) {
        options?.onEvent?.({ event: "intent", data: { intent: data.intent } });
      }
      if (data?.answer) {
        options?.onEvent?.({ event: "text_delta", data: { delta: data.answer } });
      }
      if (data?.research_result) {
        options?.onEvent?.({ event: "research_result", data: data.research_result });
      }
      if (data?.developer_result) {
        options?.onEvent?.({ event: "developer_result", data: data.developer_result });
      }
      options?.onEvent?.({ event: "done", data });
      return;
    }

    if (!response.body) {
      throw new ApiError(500, "ReadableStream not supported by browser environment.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const lines = part.split("\n");
          let eventType = "message";
          let dataStr = "";

          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith("data:")) {
              dataStr += line.slice(5).trim();
            }
          }

          if (dataStr) {
            try {
              const data = JSON.parse(dataStr);
              options?.onEvent?.({ event: eventType, data });
            } catch {
              options?.onEvent?.({ event: eventType, data: dataStr });
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }
}

export const api = new ApiAdapter();

if (typeof window !== "undefined") {
  (window as unknown as { api?: typeof api }).api = api;
}
