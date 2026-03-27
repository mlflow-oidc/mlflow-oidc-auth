import { getActiveWorkspace } from "../../shared/context/workspace-context";

export type RequestOptions = Omit<RequestInit, "body"> & {
  params?: Record<string, string>;
  body?: string;
};

const buildUrl = (url: string, params?: Record<string, string>) => {
  if (!params) return url;
  const u = new URL(url, window.location.origin);
  Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
  return u.toString();
};

/**
 * Extract a user-friendly error message from an HTTP error.
 * Falls back to the provided default message if parsing fails.
 */
export function extractErrorMessage(
  error: unknown,
  fallback: string,
): string {
  if (error instanceof Error) {
    // Error format from http(): "HTTP 400: {json body}"
    const match = error.message.match(/^HTTP \d+: (.+)$/s);
    if (match) {
      try {
        const body = JSON.parse(match[1]) as {
          message?: string;
          error_code?: string;
        };
        if (body.message) return body.message;
      } catch {
        // Response body was not JSON — use the raw text after "HTTP NNN: "
        return match[1];
      }
    }
  }
  return fallback;
}

export async function http<T = unknown>(
  url: string,
  options: RequestOptions = {},
): Promise<T> {
  const { params, ...rest } = options;

  const workspace = getActiveWorkspace();
  const workspaceHeaders: Record<string, string> = workspace
    ? { "X-MLFLOW-WORKSPACE": workspace }
    : {};

  const res = await fetch(buildUrl(url, params), {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...workspaceHeaders,
      ...(rest.headers || {}),
    },
    credentials: "include",
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}
