import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  apiRequest,
  apiRequestWithHeaders,
  apiRequestWithStatus,
  buildApiPath,
  type ApiResponse,
} from "./typed-http";
import { _resetReauthForTests } from "./http";

vi.mock("../../shared/context/active-workspace", () => ({
  getActiveWorkspace: vi.fn(() => null),
}));
vi.mock("../../shared/services/runtime-config", () => ({
  getRuntimeConfig: vi.fn(() =>
    Promise.resolve({
      basePath: "/mlflow",
      uiPath: "/mlflow/oidc/ui",
      provider: "",
      authenticated: true,
      gen_ai_gateway_enabled: false,
      workspaces_enabled: true,
    }),
  ),
}));

import { getActiveWorkspace } from "../../shared/context/active-workspace";

globalThis.fetch = vi.fn<typeof fetch>();

const jsonResponse = (body: unknown, status = 200) =>
  ({
    ok: status < 400,
    status,
    statusText: "",
    headers: new Headers({
      "content-type": "application/json",
      "X-Total-Count": "7",
    }),
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  }) as Response;

describe("buildApiPath", () => {
  it("substitutes and encodes path parameters", () => {
    expect(
      buildApiPath("/api/2.0/mlflow/users/{username}/sessions/{session_pk}", {
        username: "a/b c",
        session_pk: 3,
      }),
    ).toBe("/api/2.0/mlflow/users/a%2Fb%20c/sessions/3");
  });

  it("refuses a missing path parameter", () => {
    expect(() =>
      buildApiPath("/api/2.0/mlflow/users/{username}/active", {}),
    ).toThrow('Missing path parameter "username"');
  });
});

describe("typed-http", () => {
  beforeEach(() => {
    vi.mocked(fetch).mockReset();
    vi.mocked(getActiveWorkspace).mockReturnValue(null);
    _resetReauthForTests();
  });

  it("goes through http.ts: base path, credentials and JSON body", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({
        username: "alice",
        display_name: "Alice",
        is_admin: false,
        is_service_account: false,
        active: false,
        managed_by: "manual",
        service_account_source: null,
      }),
    );

    const user = await apiRequest(
      "patch",
      "/api/2.0/mlflow/users/{username}/active",
      { path: { username: "alice" }, body: { active: false } },
    );

    expect(user.active).toBe(false);
    expect(fetch).toHaveBeenCalledWith(
      "/mlflow/api/2.0/mlflow/users/alice/active",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ active: false }),
        credentials: "include",
      }),
    );
  });

  it("keeps the workspace header and serializes query parameters", async () => {
    vi.mocked(getActiveWorkspace).mockReturnValue("team-a");
    vi.mocked(fetch).mockResolvedValue(jsonResponse(["alice"]));

    await apiRequest("get", "/api/2.0/mlflow/users", {
      query: { service: true, limit: 10 },
    });

    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("/mlflow/api/2.0/mlflow/users?service=true&limit=10");
    expect(init?.headers).toMatchObject({ "X-MLFLOW-WORKSPACE": "team-a" });
    expect(init?.method).toBe("GET");
  });

  it("returns status and headers when asked", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse({ message: "ok" }, 201));

    const created = await apiRequestWithStatus(
      "post",
      "/api/2.0/mlflow/users",
      {
        body: {
          username: "bob",
          display_name: "Bob",
        },
      },
    );
    expect(created.status).toBe(201);

    vi.mocked(fetch).mockResolvedValue(jsonResponse(["alice"]));
    const page = await apiRequestWithHeaders("get", "/api/2.0/mlflow/users");
    expect(page.headers.get("X-Total-Count")).toBe("7");
  });

  it("a 204 resolves to undefined", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      status: 204,
      statusText: "",
      headers: new Headers(),
    } as Response);

    const result = await apiRequest(
      "delete",
      "/api/3.0/mlflow/permissions/workspaces/{workspace}/users/{username}",
      { path: { workspace: "ws", username: "alice" } },
    );
    expect(result).toBeUndefined();
  });

  it("a 401 still throws", async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: false,
      status: 401,
      statusText: "",
      headers: new Headers(),
      text: () => Promise.resolve("unauthorized"),
    } as Response);
    const assign = vi.fn();
    vi.stubGlobal("location", {
      ...window.location,
      pathname: "/mlflow/oidc/ui/user",
      search: "",
      hash: "",
      assign,
    });

    await expect(
      apiRequest("get", "/api/2.0/mlflow/users/current"),
    ).rejects.toThrow("HTTP 401");
    expect(assign).toHaveBeenCalledWith(
      "/login?next=" + encodeURIComponent("/mlflow/oidc/ui/user"),
    );
    vi.unstubAllGlobals();
  });

  it("is checked against the contract at compile time", () => {
    // Response types come from the generated contract.
    const detail: ApiResponse<
      "/api/2.0/mlflow/users/details",
      "get"
    >[number] = {
      username: "a",
      display_name: "A",
      is_admin: false,
      is_service_account: false,
      active: true,
      managed_by: "manual",
    };
    expect(detail.username).toBe("a");

    const neverCalled = () => {
      // @ts-expect-error -- not a path in the contract
      void apiRequest("get", "/api/2.0/mlflow/no-such-endpoint");
      // @ts-expect-error -- the path parameter is required
      void apiRequest("patch", "/api/2.0/mlflow/users/{username}/active", {
        body: { active: true },
      });
      void apiRequest("patch", "/api/2.0/mlflow/users/{username}/active", {
        path: { username: "a" },
        // @ts-expect-error -- `active` must be a boolean
        body: { active: "yes" },
      });
      // @ts-expect-error -- GET is not served on this path
      void apiRequest("get", "/api/2.0/mlflow/users/{username}/active", {
        path: { username: "a" },
      });
    };
    expect(neverCalled).toBeTypeOf("function");
  });
});
