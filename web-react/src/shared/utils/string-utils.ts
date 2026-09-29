export function removeTrailingSlashes(input?: string | null): string {
  const s = `${input ?? ""}`;
  let end = s.length;
  while (end > 0 && s.charAt(end - 1) === "/") {
    end--;
  }
  return s.slice(0, end);
}

/**
 * Encodes a value for use as a URL path parameter in React Router.
 * Encodes only characters that would break routing or URL structure (%, /, ?, #),
 * while keeping others like '@' readable in the address bar.
 */
export const encodeRouteParam = (value: string): string => {
  return value
    .replace(/%/g, "%25")
    .replace(/\//g, "%2F")
    .replace(/\?/g, "%3F")
    .replace(/#/g, "%23");
};

/**
 * Builds the in-app path to an entity's detail page, e.g.
 * `buildEntityRoute("/users", "a b@x.com", "/experiments")` →
 * `/users/a b@x.com/experiments`. The entity id is passed through
 * {@link encodeRouteParam} so ids containing `/`, `?`, `#` or `%` stay a
 * single path segment.
 */
export const buildEntityRoute = (
  route: string,
  entityId: string,
  suffix = "",
): string => {
  const normalizedRoute = route.replace(/^\/+/, "");
  return `/${normalizedRoute}/${encodeRouteParam(entityId)}${suffix}`;
};
