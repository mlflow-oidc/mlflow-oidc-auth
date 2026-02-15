import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AiSecretsPermissionPage from "./ai-secrets-permissions-page";
import { useGatewaySecretUserPermissions } from "../../core/hooks/use-gateway-secret-user-permissions";
import { useGatewaySecretGroupPermissions } from "../../core/hooks/use-gateway-secret-group-permissions";
import { MemoryRouter, Route, Routes } from "react-router";

// Mock hooks
vi.mock("../../core/hooks/use-gateway-secret-user-permissions");
vi.mock("../../core/hooks/use-gateway-secret-group-permissions");
vi.mock("../permissions/components/entity-permissions-page-layout", () => ({
  EntityPermissionsPageLayout: ({ title }: { title: string }) => (
    <div>{title}</div>
  ),
}));

describe("AiSecretsPermissionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state when both user and group permissions are loading", () => {
    vi.mocked(useGatewaySecretUserPermissions).mockReturnValue({
      isLoading: true,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });
    vi.mocked(useGatewaySecretGroupPermissions).mockReturnValue({
      isLoading: true,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter
        initialEntries={["/ai-gateway/secrets/test-key/permissions"]}
      >
        <Routes>
          <Route
            path="/ai-gateway/secrets/:name/permissions"
            element={<AiSecretsPermissionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByText("Permissions for Secret test-key"),
    ).toBeInTheDocument();
  });

  it("renders error state when user permissions fails", () => {
    vi.mocked(useGatewaySecretUserPermissions).mockReturnValue({
      isLoading: false,
      error: new Error("User permission error"),
      permissions: [],
      refresh: vi.fn(),
    });
    vi.mocked(useGatewaySecretGroupPermissions).mockReturnValue({
      isLoading: false,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter
        initialEntries={["/ai-gateway/secrets/test-key/permissions"]}
      >
        <Routes>
          <Route
            path="/ai-gateway/secrets/:name/permissions"
            element={<AiSecretsPermissionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByText("Permissions for Secret test-key"),
    ).toBeInTheDocument();
  });

  it("renders without key shows error message", () => {
    render(
      <MemoryRouter initialEntries={["/ai-gateway/secrets/permissions"]}>
        <Routes>
          <Route
            path="/ai-gateway/secrets/permissions"
            element={<AiSecretsPermissionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Secret Key is required.")).toBeInTheDocument();
  });
});
