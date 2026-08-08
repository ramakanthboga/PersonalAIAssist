import { getAccessToken, clearTokens, refreshAccessToken } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

function redirectToLogin(): void {
  clearTokens();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
}

async function handleUnauthorized(): Promise<boolean> {
  const refreshed = await refreshAccessToken();
  if (!refreshed) {
    redirectToLogin();
    return false;
  }
  return true;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  _retried = false,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...options.headers,
    },
  });

  if (res.status === 401) {
    if (!_retried && (await handleUnauthorized())) {
      return apiFetch<T>(path, options, true);
    }
    redirectToLogin();
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `API error ${res.status}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const text = await res.text();
  if (!text) {
    return undefined as T;
  }
  return JSON.parse(text) as T;
}

export async function apiUpload<T>(
  path: string,
  file: File,
  _retried = false,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(url, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (res.status === 401) {
    if (!_retried && (await handleUnauthorized())) {
      return apiUpload<T>(path, file, true);
    }
    redirectToLogin();
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `Upload failed`);
  }
  return res.json();
}

export function getSSEUrl(path: string): string {
  return `${API_BASE}${path}`;
}
