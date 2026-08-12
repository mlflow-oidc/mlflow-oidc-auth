import { describe, it, expect, vi, afterEach } from "vitest";

import { fetchProviders, withNextTarget } from "./provider-service";

const ok = (body: unknown) =>
  ({ ok: true, json: () => Promise.resolve(body) }) as Response;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchProviders", () => {
  it("returns the providers the server offers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          ok({
            providers: [
              {
                id: "entra",
                display_name: "Entra ID",
                type: "oidc",
                login_url: "/api/login/entra",
              },
            ],
          }),
        ),
      ),
    );

    await expect(fetchProviders("/api")).resolves.toEqual([
      {
        id: "entra",
        display_name: "Entra ID",
        type: "oidc",
        login_url: "/api/login/entra",
      },
    ]);
  });

  it("returns none when the endpoint does not exist", async () => {
    // A server from before #316. The page then renders the single-provider login it always had,
    // rather than an empty picker.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: false } as Response)),
    );

    await expect(fetchProviders("/api")).resolves.toEqual([]);
  });

  it("returns none when the body is not a provider list", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(ok({ unexpected: true }))),
    );

    await expect(fetchProviders("/api")).resolves.toEqual([]);
  });

  it("drops entries with nothing to render or nowhere to go", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          ok({
            providers: [
              {
                id: "",
                display_name: "Nameless",
                type: "oidc",
                login_url: "/x",
              },
              { id: "nowhere", display_name: "Nowhere", type: "oidc" },
              {
                id: "entra",
                display_name: "Entra ID",
                type: "oidc",
                login_url: "/api/login/entra",
              },
            ],
          }),
        ),
      ),
    );

    const providers = await fetchProviders("/api");

    expect(providers.map((provider) => provider.id)).toEqual(["entra"]);
  });

  it("drops any login URL that would leave this origin", async () => {
    // The one field that becomes an href. A response that points a sign-in button at another
    // host produces a pixel-perfect phishing page served from the real product, so the check
    // is here rather than trusting whatever produced the response.
    const hostile = [
      "//evil.example/login",
      "https://evil.example/login",
      "javascript:alert(1)",
      "data:text/html,<h1>hi",
      "login/relative",
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          ok({
            providers: hostile.map((login_url, index) => ({
              id: `p${index}`,
              display_name: "Sign in",
              type: "oidc",
              login_url,
            })),
          }),
        ),
      ),
    );

    await expect(fetchProviders("/api")).resolves.toEqual([]);
  });

  it("drops an entry whose label is not text", async () => {
    // `display_name` is rendered as a React child, so an object there throws during render and
    // takes the login page down. Dropping the entry leaves a page that still works.
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          ok({
            providers: [
              {
                id: "entra",
                display_name: { en: "Entra ID" },
                type: "oidc",
                login_url: "/login/entra",
              },
            ],
          }),
        ),
      ),
    );

    await expect(fetchProviders("/api")).resolves.toEqual([]);
  });

  it("keeps an entry with no label at all", async () => {
    // The picker falls back to the id, so a missing label is a button with words on it.
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          ok({
            providers: [
              { id: "entra", type: "oidc", login_url: "/login/entra" },
            ],
          }),
        ),
      ),
    );

    const providers = await fetchProviders("/api");

    expect(providers.map((provider) => provider.id)).toEqual(["entra"]);
  });

  it("drops entries whose fields are not strings", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          ok({
            providers: [
              { id: 7, display_name: "Numeric", type: "oidc", login_url: "/x" },
              { id: "ok", display_name: "Fine", type: "oidc", login_url: 42 },
            ],
          }),
        ),
      ),
    );

    await expect(fetchProviders("/api")).resolves.toEqual([]);
  });
});

describe("withNextTarget", () => {
  it("leaves the URL alone when there is no return target", () => {
    expect(withNextTarget("/api/login/entra", null)).toBe("/api/login/entra");
  });

  it("appends the target", () => {
    expect(withNextTarget("/api/login/entra", "/oidc/ui/models")).toBe(
      "/api/login/entra?next=%2Foidc%2Fui%2Fmodels",
    );
  });

  it("appends to a URL that already has a query", () => {
    expect(withNextTarget("/api/login/entra?a=b", "/models")).toBe(
      "/api/login/entra?a=b&next=%2Fmodels",
    );
  });

  it("encodes a target that would otherwise change the query", () => {
    expect(withNextTarget("/api/login/entra", "/a?b=c&d=e")).toBe(
      "/api/login/entra?next=%2Fa%3Fb%3Dc%26d%3De",
    );
  });

  it("passes a hostile target through for the server to reject", () => {
    // Deliberately not validated here: the server owns that decision, and a second
    // implementation would be a second thing to keep correct.
    expect(withNextTarget("/api/login/entra", "//evil.example")).toBe(
      "/api/login/entra?next=%2F%2Fevil.example",
    );
  });
});
