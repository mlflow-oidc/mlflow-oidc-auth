import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AiEndpointsPermissionPage from "./ai-endpoints-permission-page";
import { useGatewayEndpointUserPermissions } from "../../core/hooks/use-gateway-endpoint-user-permissions";
import { useGatewayEndpointGroupPermissions } from "../../core/hooks/use-gateway-endpoint-group-permissions";
import { MemoryRouter, Route, Routes } from "react-router";

// Mock hooks
vi.mock("../../core/hooks/use-gateway-endpoint-user-permissions");
vi.mock("../../core/hooks/use-gateway-endpoint-group-permissions");
vi.mock("../permissions/components/entity-permissions-manager", () => ({
  EntityPermissionsManager: () => <div data-testid="permissions-manager" />,
}));

describe("AiEndpointsPermissionPage", () => {
  const mockParams = { name: "test-endpoint" };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders permissions manager when loading is complete", () => {
    vi.mocked(useGatewayEndpointUserPermissions).mockReturnValue({
      isLoading: false,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });
    vi.mocked(useGatewayEndpointGroupPermissions).mockReturnValue({
      isLoading: false,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter
        initialEntries={[`/ai-gateway/endpoints/${mockParams.name}`]}
      >
        <Routes>
          <Route
            path="/ai-gateway/endpoints/:name"
            element={<AiEndpointsPermissionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByText("Permissions for Endpoint test-endpoint"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });

  it("displays error message if name param is missing", () => {
    render(
      <MemoryRouter initialEntries={["/ai-gateway/endpoints/"]}>
        <Routes>
          <Route
            path="/ai-gateway/endpoints/"
            element={<AiEndpointsPermissionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("Endpoint Name is required.")).toBeInTheDocument();
  });

  it("passes loading state to manager", () => {
    vi.mocked(useGatewayEndpointUserPermissions).mockReturnValue({
      isLoading: true,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });
    vi.mocked(useGatewayEndpointGroupPermissions).mockReturnValue({
      isLoading: false,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter
        initialEntries={[`/ai-gateway/endpoints/${mockParams.name}`]}
      >
        <Routes>
          <Route
            path="/ai-gateway/endpoints/:name"
            element={<AiEndpointsPermissionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();
  });
});
