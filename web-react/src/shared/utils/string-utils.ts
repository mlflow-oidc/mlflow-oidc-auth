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
