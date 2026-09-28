/**
 * The identity providers a browser may log in with (issue #317).
 *
 * Reads the endpoint #316 added. It is deliberately unauthenticated and deliberately thin — an
 * id, a label, a type and a login URL — because it is fetched before anyone has signed in.
 *
 * `type` is carried through unvalidated and used only for a label. This file itself stays
 * agnostic to what kind of provider it is fetching, so the SAML providers in #330 appear without
 * this file changing.
 */

/**
 * The kinds of provider the picker knows to label (#330). The `| string` keeps any other value
 * — a type this file has never heard of — assignable and rendering exactly as it does today,
 * with no kind label. ESLint's `no-redundant-type-constituents` flags the literals as redundant
 * with `string`; that is true for assignability and is the point here (unknown types still
 * type-check), while the literals stay for readability and editor autocomplete at call sites.
 */
// eslint-disable-next-line @typescript-eslint/no-redundant-type-constituents
export type ProviderType = "oidc" | "saml" | string;

export type IdentityProvider = {
  id: string;
  display_name: string;
  type: ProviderType;
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
 * The `typeof` checks are not ceremony. `id` and `login_url` become an attribute and a React
 * key, where a non-string would be stringified rather than rejected — but `display_name` is
 * rendered as a React *child*, and an object there throws during render and takes the whole
 * login page down with it. Absent is fine: the label falls back to `id`.
 */
function isRenderable(provider: IdentityProvider): boolean {
  return (
    Boolean(provider) &&
    typeof provider.id === "string" &&
    provider.id.length > 0 &&
    (provider.display_name === undefined ||
      provider.display_name === null ||
      typeof provider.display_name === "string") &&
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

/**
 * Prefix a provider's `login_url` with the app's base path when the two disagree.
 *
 * `login_url` is built server-side from `root_path`, which the server only sets for a *trusted*
 * proxy hop. `basePath` (config.ts) is read from `X-Forwarded-Prefix` unconditionally — any hop
 * can set that header. Behind an untrusted proxy the two can disagree: the app is served under
 * `basePath` (e.g. `/mlflow`) but `login_url` comes back unprefixed (e.g. `/login/default`), so a
 * login button built from `login_url` alone points somewhere the proxy does not route.
 *
 * A `login_url` that already lives under `basePath` (the trusted-hop case, and every server from
 * before this existed) is returned unchanged. `isRenderable`'s same-origin, single-leading-slash
 * check already ran on `login_url` before this is called, and simple concatenation of two
 * single-leading-slash paths preserves that shape.
 */
export function resolveLoginUrl(loginUrl: string, basePath: string): string {
  if (!basePath) return loginUrl;
  if (loginUrl === basePath || loginUrl.startsWith(`${basePath}/`)) {
    return loginUrl;
  }
  return `${basePath}${loginUrl}`;
}
