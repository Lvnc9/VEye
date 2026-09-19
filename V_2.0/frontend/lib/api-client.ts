/**
 * Fetch wrapper for the VEye V2 backend (see skeleton.md §4).
 *
 * - Base URL comes from NEXT_PUBLIC_API_BASE_URL.
 * - Always sends credentials: 'include' so the httpOnly access/refresh
 *   cookies set by /auth/login/ are attached automatically.
 * - Reads the readable `csrftoken` cookie (double-submit CSRF, skeleton.md
 *   §4) and attaches it as X-CSRFToken on mutating requests.
 * - On a 401, attempts one silent POST /auth/refresh/ and retries the
 *   original request once before giving up and redirecting to /login.
 *
 * This module is intended for CLIENT-SIDE use only (all pages that call it
 * are "use client" components fetching in useEffect/event handlers) — see
 * the frontend build report for why: it keeps `next build` from ever
 * needing a reachable backend, and httpOnly-cookie + CSRF-header auth is
 * inherently a browser-side concern anyway.
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

type QueryParams = Record<string, string | number | boolean | undefined | null>;

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const escaped = name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1");
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function buildUrl(path: string, params?: QueryParams): string {
  const base = path.startsWith("http")
    ? path
    : `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`;
  const url = new URL(base);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}

let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/refresh/`, {
          method: "POST",
          credentials: "include",
          headers: { "X-CSRFToken": getCookie("csrftoken") ?? "" },
        });
        return res.ok;
      } catch {
        return false;
      }
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

const SESSION_ENDPOINTS = /^\/auth\/(login|refresh|logout)\/?$/;

/**
 * Turns an error body into one readable Persian message.
 *
 * The backend sends either `{ detail: "..." }` (permission errors, conflicts,
 * bad credentials) or DRF field errors `{ title: ["..."], group: ["..."] }`
 * for validation failures. Both are flattened; anything else falls back to a
 * generic message rather than leaking an English status line into the UI.
 */
function extractErrorMessage(data: unknown, status: number): string {
  if (typeof data === "object" && data !== null) {
    const body = data as Record<string, unknown>;
    if (typeof body.detail === "string" && body.detail) return body.detail;

    const messages = Object.values(body).flatMap((value) =>
      Array.isArray(value)
        ? value.filter((item): item is string => typeof item === "string")
        : typeof value === "string"
          ? [value]
          : [],
    );
    if (messages.length > 0) return messages.join(" ");
  }
  return `درخواست ناموفق بود (کد ${status}).`;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  params?: QueryParams;
  body?: BodyInit | null;
  /** Internal: prevents infinite refresh loops. */
  _isRetry?: boolean;
}

async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { params, _isRetry, ...init } = options;
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);

  const isFormData = init.body instanceof FormData;
  if (init.body && !isFormData && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (MUTATING_METHODS.has(method)) {
    const csrfToken = getCookie("csrftoken");
    if (csrfToken) headers.set("X-CSRFToken", csrfToken);
  }

  const response = await fetch(buildUrl(path, params), {
    ...init,
    method,
    headers,
    credentials: "include",
  });

  // A 401 from login/refresh/logout is an answer, not an expired session:
  // a wrong password is a 401 too, and must reach the caller as an error message
  // rather than triggering a refresh attempt and a hard reload of /login.
  if (response.status === 401 && !_isRetry && !SESSION_ENDPOINTS.test(path)) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      return apiRequest<T>(path, { ...options, _isRetry: true });
    }
    if (typeof window !== "undefined") {
      // Deliberate full-page navigation: a dead session should drop all client state.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/login";
    }
    throw new ApiError("نشست شما منقضی شده است. لطفاً دوباره وارد شوید.", 401);
  }

  if (!response.ok) {
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      data = undefined;
    }
    throw new ApiError(extractErrorMessage(data, response.status), response.status, data);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }
  return undefined as T;
}

export function apiGet<T>(path: string, params?: QueryParams): Promise<T> {
  return apiRequest<T>(path, { method: "GET", params });
}

export function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function apiPatch<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "PATCH",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>(path, {
    method: "PUT",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export function apiDelete<T>(path: string): Promise<T> {
  return apiRequest<T>(path, { method: "DELETE" });
}

/** Multipart upload helper for poster attachments/insurance documents. */
export function apiUpload<T>(
  path: string,
  formData: FormData,
  method: "POST" | "PATCH" | "PUT" = "POST",
): Promise<T> {
  return apiRequest<T>(path, { method, body: formData });
}

export interface UploadOptions {
  /** Called with a 0..1 fraction as bytes are sent. */
  onProgress?: (fraction: number) => void;
  /** Abort the upload (V_1.0 had a "Cancel Upload" button, utils.py:2350). */
  signal?: AbortSignal;
}

/**
 * Multipart POST with upload progress. `fetch` can't report upload progress,
 * so this uses XMLHttpRequest — carrying the same cookie + CSRF handling and the
 * same one-shot silent refresh on a 401 as `apiRequest`.
 */
export function apiUploadWithProgress<T>(
  path: string,
  formData: FormData,
  options: UploadOptions = {},
): Promise<T> {
  const attempt = (isRetry: boolean): Promise<T> =>
    new Promise<T>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", buildUrl(path));
      xhr.withCredentials = true;
      const csrfToken = getCookie("csrftoken");
      if (csrfToken) xhr.setRequestHeader("X-CSRFToken", csrfToken);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) options.onProgress?.(event.loaded / event.total);
      };
      xhr.onload = async () => {
        let data: unknown;
        try {
          data = JSON.parse(xhr.responseText);
        } catch {
          data = undefined;
        }
        if (xhr.status === 401 && !isRetry) {
          if (await refreshAccessToken()) {
            attempt(true).then(resolve, reject);
            return;
          }
          // Deliberate full-page navigation: a dead session should drop all client state.
          // eslint-disable-next-line @next/next/no-location-assign-relative-destination
          if (typeof window !== "undefined") window.location.href = "/login";
          reject(new ApiError("نشست شما منقضی شده است. لطفاً دوباره وارد شوید.", 401));
          return;
        }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data as T);
          return;
        }
        reject(new ApiError(extractErrorMessage(data, xhr.status), xhr.status, data));
      };
      xhr.onerror = () => reject(new ApiError("ارتباط با سرور برقرار نشد.", 0));
      xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
      options.signal?.addEventListener("abort", () => xhr.abort(), { once: true });
      xhr.send(formData);
    });

  return attempt(false);
}

export { API_BASE_URL };
