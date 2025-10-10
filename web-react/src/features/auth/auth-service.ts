import { http } from "../../core/services/http";

export type RuntimeConfig = {
  basePath?: string;
  uiPath?: string;
  provider?: string;
  authenticated?: boolean;
};

const ENDPOINTS = {
  CURRENT_USER: "/api/2.0/mlflow/permissions/users/current",
};

export async function fetchRuntimeConfig(): Promise<RuntimeConfig> {
  try {
    // Use relative path - works because config.json is served from same UI path
    const response = await fetch("config.json");

    if (response.ok) return (await response.json()) as RuntimeConfig;
    console.warn(`Failed to load runtime config: HTTP ${response.status}`);
  } catch (error) {
    console.warn("Failed to load runtime config:", error);
  }
  // Fallback: infer configuration from current URL
  return inferConfigFromCurrentUrl();
}

/**
 * Infer runtime configuration from the current URL when all fetch attempts fail
 */
function inferConfigFromCurrentUrl(): RuntimeConfig {
  const segments = window.location.pathname.split("/").filter(Boolean);
  let inferredBasePath = "";
  const oidcIndex = segments.indexOf("oidc");
  if (oidcIndex > 0)
    inferredBasePath = `/${segments.slice(0, oidcIndex).join("/")}`;
  else if (segments.length > 0 && segments[0] !== "oidc")
    inferredBasePath = `/${segments[0]}`;

  return {
    basePath: inferredBasePath,
    uiPath: `${inferredBasePath}/oidc/ui`,
    authenticated: false,
    provider: "Login with Test",
  };
}

/**
 * Update the base href in the document head
 */
export function updateBaseHref(basePath: string): void {
  const normalizedBasePath = basePath.endsWith("/") ? basePath : `${basePath}/`;

  let baseTag = document.querySelector("base") as HTMLBaseElement;
  if (!baseTag) {
    baseTag = document.createElement("base");
    const head = document.querySelector("head");
    if (head) {
      head.appendChild(baseTag);
    }
  }

  baseTag.href = normalizedBasePath;
}

export async function fetchCurrentUser(): Promise<unknown> {
  return http<unknown>(ENDPOINTS.CURRENT_USER, { method: "GET" });
}

// Helper to build an /auth url preserving query params and hash params
export const buildAuthUrlWithParams = (): {
  href: string;
  queryParams?: Record<string, string | string[]>;
} => {
  const { search, hash } = window.location;

  // collect query params from location.search
  const qp = new URLSearchParams(search || "");
  const queryParams: Record<string, string | string[]> = {};
  qp.forEach((value, key) => {
    if (!queryParams[key]) queryParams[key] = [];
    (queryParams[key] as string[]).push(value);
  });

  // If hash contains something like #/auth?foo=bar, extract those params too
  const hashMatch = hash.match(/#\/auth\?(.+)/);
  if (hashMatch && hashMatch[1]) {
    const h = new URLSearchParams(hashMatch[1]);
    h.forEach((value, key) => {
      if (!queryParams[key]) queryParams[key] = [];
      (queryParams[key] as string[]).push(value);
    });
  }

  // Build a search string for /auth (make it relative to the current app base path)
  const combined = new URLSearchParams();
  Object.keys(queryParams).forEach((k) => {
    const v = queryParams[k];
    if (Array.isArray(v)) v.forEach((vv) => combined.append(k, vv));
    else combined.append(k, String(v));
  });

  // Determine a sensible base for the SPA. Prefer the current pathname (strip trailing slash).
  // This keeps the redirect inside the SPA base (e.g. /oidc/ui/auth) instead of navigating to /auth.
  const pathnameBase = window.location.pathname.replace(/\/+$|\/$/, "");
  const href = `${pathnameBase}/auth${
    combined.toString() ? `?${combined.toString()}` : ""
  }`;
  return {
    href,
    queryParams: Object.keys(queryParams).length ? queryParams : undefined,
  };
};
