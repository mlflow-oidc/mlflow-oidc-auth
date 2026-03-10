import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AiEndpointsPage from "./ai-endpoints-page";
import { useAllGatewayEndpoints } from "../../core/hooks/use-all-gateway-endpoints";
import { MemoryRouter } from "react-router";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";

// Mock hooks
vi.mock("../../core/hooks/use-all-gateway-endpoints");
vi.mock("../../shared/context/use-runtime-config"); // Mock useRuntimeConfig

const mockEndpoints = [
  {
    name: "endpoint-1",
    type: "llm/v1/chat",
    description: "test endpoint 1",
    route_type: "llm/v1/chat",
    auth_type: "bearer",
  },
  {
    name: "endpoint-2",
    type: "llm/v1/completions",
    description: "test endpoint 2",
    route_type: "llm/v1/completions",
    auth_type: "bearer",
  },
];

describe("AiEndpointsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRuntimeConfig).mockReturnValue({
      basePath: "",
      uiPath: "/",
      provider: "local",
      authenticated: true,
      gen_ai_gateway_enabled: true,
    }); // Mock runtime config
  });

  it("renders loading state", () => {
    vi.mocked(useAllGatewayEndpoints).mockReturnValue({
      isLoading: true,
      error: null,
      allGatewayEndpoints: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiEndpointsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Loading endpoints list...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    vi.mocked(useAllGatewayEndpoints).mockReturnValue({
      isLoading: false,
      error: new Error("Test error"),
      allGatewayEndpoints: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiEndpointsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Error: Test error/i)).toBeInTheDocument();
  });

  it("renders endpoints list", () => {
    vi.mocked(useAllGatewayEndpoints).mockReturnValue({
      isLoading: false,
      error: null,
      allGatewayEndpoints: mockEndpoints,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiEndpointsPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("endpoint-1")).toBeInTheDocument();
    expect(screen.getByText("endpoint-2")).toBeInTheDocument();
    expect(screen.getByText("llm/v1/chat")).toBeInTheDocument();
  });

  it("filters endpoints by search term", () => {
    vi.mocked(useAllGatewayEndpoints).mockReturnValue({
      isLoading: false,
      error: null,
      allGatewayEndpoints: mockEndpoints,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiEndpointsPage />
      </MemoryRouter>,
    );

    const searchInput = screen.getByPlaceholderText("Search endpoints...");
    fireEvent.change(searchInput, { target: { value: "endpoint-1" } });
    fireEvent.submit(searchInput);

    expect(screen.getByText("endpoint-1")).toBeInTheDocument();
    expect(screen.queryByText("endpoint-2")).not.toBeInTheDocument();
  });

  it("renders permission buttons", () => {
    vi.mocked(useAllGatewayEndpoints).mockReturnValue({
      isLoading: false,
      error: null,
      allGatewayEndpoints: mockEndpoints,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiEndpointsPage />
      </MemoryRouter>,
    );

    const permissionButtons = screen.getAllByText("Manage permissions");
    expect(permissionButtons).toHaveLength(2);
  });
});
