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

let reauthTriggered = false;

/**
 * Reset the reauth latch — exposed for tests so each case starts clean.
 */
export function _resetReauthForTests(): void {
  reauthTriggered = false;
}

/**
 * Navigate to the OIDC login flow once on 401. /oidc/ui is in the auth
 * middleware's unprotected prefix list, so a plain reload would just bring
 * the SPA back into the same broken state — we have to actively redirect to
 * /login. Skips the redirect on the auth feature page itself, which legitimately
 * receives 401-ish responses while a logged-out user is on it.
 */
function triggerReauth(): void {
  if (reauthTriggered) return;
  if (typeof window === "undefined") return;
  const pathname = window.location.pathname;
  if (pathname.includes("/oidc/ui/auth")) return;
  reauthTriggered = true;
  const baseHref = document.querySelector("base")?.getAttribute("href") ?? "/";
  const loginUrl = baseHref.replace(/\/$/, "") + "/login";
  window.location.assign(loginUrl);
}

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
    if (res.status === 401) {
      triggerReauth();
    }
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }

  // 204 No Content — nothing to parse
  if (res.status === 204) return undefined as unknown as T;

  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}
