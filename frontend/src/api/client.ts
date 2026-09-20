// Central HTTP client. Every network call in the app goes through here so
// that auth headers, refresh, and error shaping happen in exactly one place.
//
// VITE_API_BASE_URL points at the FastAPI backend (see backend/app/main.py).
// Nothing in this file talks to a local database — if the backend is
// unreachable, callers fall back to the offline queue (see
// src/services/offlineDb.ts and src/services/syncService.ts), not to fake data.

// Falls back to the standard local-dev backend address (and logs a loud
// warning) rather than silently sending every request to
// "http://localhost:5173/undefined/..." if frontend/.env was never created
// from .env.example — a missing-env-file mistake that previously produced a
// confusing generic "Login failed" with no indication of the real cause.
const DEFAULT_API_BASE_URL = "http://localhost:8000/api/v1";
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL;
if (!import.meta.env.VITE_API_BASE_URL) {
  // eslint-disable-next-line no-console
  console.warn(
    `[LabelLens] VITE_API_BASE_URL is not set (frontend/.env is missing or wasn't loaded — ` +
      `remember Vite only reads .env at dev-server startup, so create it and restart). ` +
      `Falling back to ${DEFAULT_API_BASE_URL}.`
  );
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function getAccessToken(): string | null {
  return localStorage.getItem("labellens.accessToken");
}

export function setTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem("labellens.accessToken", accessToken);
  localStorage.setItem("labellens.refreshToken", refreshToken);
}

export function clearTokens() {
  localStorage.removeItem("labellens.accessToken");
  localStorage.removeItem("labellens.refreshToken");
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  isFormData?: boolean;
  skipAuth?: boolean;
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem("labellens.refreshToken");
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refreshToken })
    });
    if (!res.ok) return null;
    const data = await res.json();
    setTokens(data.accessToken, data.refreshToken);
    return data.accessToken as string;
  } catch {
    return null;
  }
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, isFormData, skipAuth, headers, ...rest } = options;

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(headers as Record<string, string> | undefined)
  };

  if (!isFormData) {
    finalHeaders["Content-Type"] = "application/json";
  }

  if (!skipAuth) {
    const token = getAccessToken();
    if (token) finalHeaders["Authorization"] = `Bearer ${token}`;
  }

  const doFetch = async () =>
    fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: finalHeaders,
      body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined
    });

  let response: Response;
  try {
    response = await doFetch();
  } catch (networkErr) {
    // Distinguish "backend unreachable" from an actual HTTP error so callers
    // (e.g. inspection save) know to route through the offline queue instead.
    throw new ApiError("NETWORK_UNREACHABLE", 0, networkErr);
  }

  if (response.status === 401 && !skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      finalHeaders["Authorization"] = `Bearer ${newToken}`;
      response = await fetch(`${API_BASE_URL}${path}`, { ...rest, headers: finalHeaders, body: isFormData ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined });
    } else {
      clearTokens();
      window.location.assign("/login");
      throw new ApiError("SESSION_EXPIRED", 401, null);
    }
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json().catch(() => null) : await response.blob();

  if (!response.ok) {
    const message = (payload && (payload as any).detail) || response.statusText;
    throw new ApiError(message, response.status, payload);
  }

  return payload as T;
}

export function isBackendUnreachable(err: unknown): boolean {
  return err instanceof ApiError && err.status === 0;
}

export { API_BASE_URL };
