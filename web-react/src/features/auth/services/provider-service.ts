/**
 * The identity providers a browser may log in with (issue #317).
 *
 * Reads the endpoint #316 added. It is deliberately unauthenticated and deliberately thin — an
 * id, a label, a type and a login URL — because it is fetched before anyone has signed in.
 *
 * Nothing here knows what an OIDC provider is. `type` is carried through and used only for a
 * label, so the SAML providers in #330 appear without this file changing.
 */

export type IdentityProvider = {
  id: string;
  display_name: string;
  type: string;
  login_url: string;
};

type ProvidersResponse = {
  providers?: IdentityProvider[];
};

/**
 * Fetch the providers a browser may use.
 *
 * Returns an empty list when the endpoint is missing or unreadable, which is what a server from
 * before #316 does. The caller then falls back to the single-provider login it has always had,
 * so an older server keeps working rather than showing an empty page.
 */
export async function fetchProviders(
  basePath: string,
  signal?: AbortSignal,
): Promise<IdentityProvider[]> {
  const response = await fetch(`${basePath}/providers`, {
    cache: "no-store",
    signal,
    headers: { Accept: "application/json" },
  });

  if (!response.ok) {
    return [];
  }

  const body = (await response.json()) as ProvidersResponse;
  if (!Array.isArray(body?.providers)) {
    return [];
  }

  return body.providers.filter(isRenderable);
}

/**
 * Whether an entry can safely become a sign-in button.
 *
 * `login_url` is the one field that becomes an `href`, so it is the one field where a wrong
 * value sends a user somewhere rather than merely rendering badly. Only a same-origin path is
 * accepted — one leading slash, never two, since `//evil.example` is a protocol-relative URL
 * that browsers resolve off-origin. That is exactly what the server emits, and it means no
 * response to this endpoint can point a login button at another host, whatever produced it.
 *
 * The `typeof` checks are not ceremony: these values go into an attribute and a React key, and
 * a non-string would be stringified rather than rejected.
 */
function isRenderable(provider: IdentityProvider): boolean {
  return (
    Boolean(provider) &&
    typeof provider.id === "string" &&
    provider.id.length > 0 &&
    typeof provider.login_url === "string" &&
    provider.login_url.startsWith("/") &&
    !provider.login_url.startsWith("//")
  );
}

/**
 * Carry a `?next=` return target onto a provider's login URL.
 *
 * Passed through verbatim: the server validates it (`_sanitize_next`), and a second
 * implementation here would be a second thing to keep correct — the one that rejects
 * `/\evil.com` because browsers resolve it off-origin, which is not obvious enough to want
 * duplicated.
 */
export function withNextTarget(loginUrl: string, next: string | null): string {
  if (!next) return loginUrl;
  const separator = loginUrl.includes("?") ? "&" : "?";
  return `${loginUrl}${separator}next=${encodeURIComponent(next)}`;
}
