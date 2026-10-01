import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";
import McpServersPermissionPage from "./mcp-servers-permission-page";
import { useMcpServerUserPermissions } from "../../core/hooks/use-mcp-server-user-permissions";
import { useMcpServerGroupPermissions } from "../../core/hooks/use-mcp-server-group-permissions";

vi.mock("../../core/hooks/use-mcp-server-user-permissions");
vi.mock("../../core/hooks/use-mcp-server-group-permissions");
vi.mock("../permissions/components/entity-permissions-manager", () => ({
  EntityPermissionsManager: (props: { resourceType: string }) => (
    <div data-testid="permissions-manager">{props.resourceType}</div>
  ),
}));

const idle = {
  isLoading: false,
  error: null,
  permissions: [],
  refresh: vi.fn(),
};

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/mcp-servers/:name"
          element={<McpServersPermissionPage />}
        />
        <Route path="/mcp-servers/" element={<McpServersPermissionPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("McpServersPermissionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useMcpServerUserPermissions).mockReturnValue(idle);
    vi.mocked(useMcpServerGroupPermissions).mockReturnValue(idle);
  });

  it("decodes the encoded slash and loads the server's grants", () => {
    renderAt("/mcp-servers/com.example%2Fweather");

    expect(
      screen.getByText("Permissions for MCP Server com.example/weather"),
    ).toBeInTheDocument();
    expect(useMcpServerUserPermissions).toHaveBeenCalledWith({
      name: "com.example/weather",
    });
    expect(useMcpServerGroupPermissions).toHaveBeenCalledWith({
      name: "com.example/weather",
    });
    expect(screen.getByTestId("permissions-manager")).toHaveTextContent(
      "mcp-servers",
    );
  });

  it("requires a name", () => {
    renderAt("/mcp-servers/");
    expect(
      screen.getByText("MCP server name is required."),
    ).toBeInTheDocument();
  });
});
