// Minimal fetch wrapper / API client
export type RequestOptions = Omit<RequestInit, "body"> & {
  params?: Record<string, string>;
};

const buildUrl = (url: string, params?: Record<string, string>) => {
  if (!params) return url;
  const u = new URL(url, window.location.origin);
  Object.entries(params).forEach(([k, v]) => u.searchParams.set(k, v));
  return u.toString();
};

export async function http<T = unknown>(
  url: string,
  options: RequestOptions = {}
): Promise<T> {
  const { params, ...rest } = options;
  const res = await fetch(buildUrl(url, params), {
    ...rest,
    headers: {
      "Content-Type": "application/json",
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
