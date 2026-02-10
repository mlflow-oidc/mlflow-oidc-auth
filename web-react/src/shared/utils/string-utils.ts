export function removeTrailingSlashes(input?: string | null): string {
  const s = `${input ?? ""}`;
  let end = s.length;
  while (end > 0 && s.charAt(end - 1) === "/") {
    end--;
  }
  return s.slice(0, end);
}
