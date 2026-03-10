import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AiModelsPermissionPage from "./ai-models-permissions-page";
import { useGatewayModelUserPermissions } from "../../core/hooks/use-gateway-model-user-permissions";
import { useGatewayModelGroupPermissions } from "../../core/hooks/use-gateway-model-group-permissions";
import { MemoryRouter, Route, Routes } from "react-router";

// Mock hooks
vi.mock("../../core/hooks/use-gateway-model-user-permissions");
vi.mock("../../core/hooks/use-gateway-model-group-permissions");
vi.mock("../permissions/components/entity-permissions-page-layout", () => ({
  EntityPermissionsPageLayout: ({ title }: { title: string }) => (
    <div>{title}</div>
  ),
}));

describe("AiModelsPermissionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state when both user and group permissions are loading", () => {
    vi.mocked(useGatewayModelUserPermissions).mockReturnValue({
      isLoading: true,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });
    vi.mocked(useGatewayModelGroupPermissions).mockReturnValue({
      isLoading: true,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter
        initialEntries={["/ai-gateway/models/test-model/permissions"]}
      >
        <Routes>
          <Route
            path="/ai-gateway/models/:name/permissions"
            element={<AiModelsPermissionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByText("Permissions for AI Model test-model"),
    ).toBeInTheDocument();
  });

  it("renders error state when user permissions fails", () => {
    vi.mocked(useGatewayModelUserPermissions).mockReturnValue({
      isLoading: false,
      error: new Error("User permission error"),
      permissions: [],
      refresh: vi.fn(),
    });
    vi.mocked(useGatewayModelGroupPermissions).mockReturnValue({
      isLoading: false,
      error: null,
      permissions: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter
        initialEntries={["/ai-gateway/models/test-model/permissions"]}
      >
        <Routes>
          <Route
            path="/ai-gateway/models/:name/permissions"
            element={<AiModelsPermissionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      screen.getByText("Permissions for AI Model test-model"),
    ).toBeInTheDocument();
  });

  it("renders without name shows error message", () => {
    render(
      <MemoryRouter initialEntries={["/ai-gateway/models/permissions"]}>
        <Routes>
          <Route
            path="/ai-gateway/models/permissions"
            element={<AiModelsPermissionPage />}
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("AI Model Name is required.")).toBeInTheDocument();
  });
});
