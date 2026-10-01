import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AiEndpointsPage from "./ai-endpoints-page";
import { pagedListState } from "../../tests/paged-list-mock";
import { fetchGatewayEndpointsPage } from "../../core/services/gateway-service";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";

// Mock hooks
const mockListSource = vi.fn();
// The list the server would page through; usePagedList is mocked to search
// it the way the server does and return it as a single page.
const mockUsePagedList = vi.fn();
vi.mock("../../core/hooks/use-paged-list", () => ({
  usePagedList: (fetchPage: unknown, search = "") => {
    mockUsePagedList(fetchPage, search);
    const { allGatewayEndpoints, isLoading, error, refresh } = mockListSource() as {
      allGatewayEndpoints: { name: string }[] | null;
      isLoading: boolean;
      error: Error | null;
      refresh: () => void;
    };
    return pagedListState(
      (allGatewayEndpoints ?? []).filter((item: { name: string }) =>
        item.name.toLowerCase().includes(search.toLowerCase()),
      ),
      { isLoading, error, refresh },
    );
  },
}));
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
      workspaces_enabled: false,
    }); // Mock runtime config
  });

  it("renders loading state", () => {
    mockListSource.mockReturnValue({
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
    mockListSource.mockReturnValue({
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
    mockListSource.mockReturnValue({
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
    mockListSource.mockReturnValue({
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

    expect(mockUsePagedList).toHaveBeenLastCalledWith(
      fetchGatewayEndpointsPage,
      "endpoint-1",
    );

    expect(screen.getByText("endpoint-1")).toBeInTheDocument();
    expect(screen.queryByText("endpoint-2")).not.toBeInTheDocument();
  });

  describe("row navigation", () => {
    function LocationDisplay() {
      const location = useLocation();
      return <div data-testid="location">{location.pathname}</div>;
    }

    const renderAtList = () =>
      render(
        <MemoryRouter initialEntries={["/list"]}>
          <Routes>
            <Route
              path="*"
              element={
                <>
                  <AiEndpointsPage />
                  <LocationDisplay />
                </>
              }
            />
          </Routes>
        </MemoryRouter>,
      );

    beforeEach(() => {
      mockListSource.mockReturnValue({
        isLoading: false,
        error: null,
        allGatewayEndpoints: [
          { ...mockEndpoints[0], name: "a b@x.com" },
          { ...mockEndpoints[1], name: "team/1" },
        ],
        refresh: vi.fn(),
      });
    });

    it("renders each name as a link to its permissions page", () => {
      renderAtList();
      expect(screen.getByRole("link", { name: "a b@x.com" })).toHaveAttribute(
        "href",
        "/ai-gateway/ai-endpoints/a b@x.com",
      );
      expect(screen.getByRole("link", { name: "team/1" })).toHaveAttribute(
        "href",
        "/ai-gateway/ai-endpoints/team%2F1",
      );
    });

    it("navigates to the same destination when the row is clicked", () => {
      renderAtList();
      const row = screen
        .getByRole("link", { name: "team/1" })
        .closest('[role="row"]');
      expect(row).not.toBeNull();
      const cells = within(row as HTMLElement).getAllByRole("cell");
      fireEvent.click(cells[cells.length - 1]);
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/ai-gateway/ai-endpoints/team%2F1",
      );
    });

    it("has no Permissions column, Manage permissions button or hidden elements", () => {
      const { container } = renderAtList();
      expect(
        screen.getByRole("columnheader", { name: "Endpoint Name" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("columnheader", { name: "Permissions" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /manage permissions/i }),
      ).not.toBeInTheDocument();
      expect(container.querySelector(".invisible")).toBeNull();
    });

    it("keeps the name link keyboard focusable", () => {
      renderAtList();
      const link = screen.getByRole("link", { name: "a b@x.com" });
      link.focus();
      expect(document.activeElement).toBe(link);
    });
  });
});
