import { getActiveWorkspace } from "../../shared/context/active-workspace";

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
 * Whether ``next`` is a same-origin path the login flow can return to.
 *
 * ``location.pathname`` can itself start with ``//`` (``https://host//evil.com``),
 * which a browser reads as a protocol-relative URL. The backend's
 * ``_sanitize_next`` already refuses it; this keeps the SPA from building the
 * redirect in the first place.
 */
function isSafeNextPath(next: string): boolean {
  return next.startsWith("/") && !next.startsWith("//") && !next.includes("\\");
}

/**
 * Navigate to the OIDC login flow once on 401. /oidc/ui is in the auth
 * middleware's unprotected prefix list, so a plain reload would just bring
 * the SPA back into the same broken state — we have to actively redirect to
 * /login. Forwards the current path/search/hash as ?next= so the callback
 * can return the user to where they were. Skips the redirect on the auth
 * feature page itself, which legitimately receives 401-ish responses while
 * a logged-out user is on it.
 *
 * The login endpoint lives at ``<basePath>/login``, NOT under the SPA's
 * ``<base href>`` (which is ``<basePath>/oidc/ui/``). Use the runtime
 * config's ``basePath`` to get the proxy prefix.
 */
function triggerReauth(): void {
  if (reauthTriggered) return;
  if (typeof window === "undefined") return;
  const pathname = window.location.pathname;
  if (pathname.includes("/oidc/ui/auth")) return;
  reauthTriggered = true;
  const runtime = (window as { __RUNTIME_CONFIG__?: { basePath?: string } })
    .__RUNTIME_CONFIG__;
  const basePath = (runtime?.basePath ?? "").replace(/\/$/, "");
  const next =
    window.location.pathname + window.location.search + window.location.hash;
  // A rejected path sends no ``next`` at all: the backend then picks its own
  // default, which carries the proxy prefix and DEFAULT_LANDING_PAGE_IS_PERMISSIONS.
  const loginUrl = isSafeNextPath(next)
    ? basePath + "/login?next=" + encodeURIComponent(next)
    : basePath + "/login";
  window.location.assign(loginUrl);
}

/**
 * Extract a user-friendly error message from an HTTP error.
 * Falls back to the provided default message if parsing fails.
 */
export function extractErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    // Error format from http(): "HTTP 400: {json body}"
    const match = error.message.match(/^HTTP \d+: (.+)$/s);
    if (match) {
      try {
        const body = JSON.parse(match[1]) as {
          message?: string;
          error_code?: string;
          detail?: string;
        };
        if (body.message) return body.message;
        // Plain FastAPI HTTPException responses use {"detail": "..."} rather
        // than the {"message": ...} shape emitted by the MlflowException
        // handler — fall back to it so 4xx refusals still surface verbatim.
        if (typeof body.detail === "string") return body.detail;
      } catch {
        // Response body was not JSON — use the raw text after "HTTP NNN: "
        return match[1];
      }
    }
  }
  return fallback;
}

export interface HttpResult<T> {
  data: T;
  status: number;
}

/** {@link HttpResult} plus the response headers. */
export interface HttpResultWithHeaders<T> extends HttpResult<T> {
  headers: Headers;
}

async function httpRaw<T = unknown>(
  url: string,
  options: RequestOptions = {},
): Promise<HttpResultWithHeaders<T>> {
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
  if (res.status === 204) {
    return {
      data: undefined as unknown as T,
      status: res.status,
      headers: res.headers,
    };
  }

  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json")
    ? ((await res.json()) as T)
    : ((await res.text()) as unknown as T);
  return { data, status: res.status, headers: res.headers };
}

export async function http<T = unknown>(
  url: string,
  options: RequestOptions = {},
): Promise<T> {
  const { data } = await httpRaw<T>(url, options);
  return data;
}

/**
 * Like {@link http}, but also returns the response's HTTP status — for the rare endpoint whose
 * status code itself is part of the response (e.g. an idempotent create returning 201 when it
 * created the resource and 200 when it already existed).
 */
export async function httpWithStatus<T = unknown>(
  url: string,
  options: RequestOptions = {},
): Promise<HttpResult<T>> {
  const { data, status } = await httpRaw<T>(url, options);
  return { data, status };
}

/**
 * Like {@link http}, but also returns the response's status and headers — for list endpoints that
 * report the total number of matching items in a header (`X-Total-Count`).
 */
export async function httpWithHeaders<T = unknown>(
  url: string,
  options: RequestOptions = {},
): Promise<HttpResultWithHeaders<T>> {
  return httpRaw<T>(url, options);
}
