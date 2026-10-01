import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AiModelsPage from "./ai-models-page";
import { pagedListState } from "../../tests/paged-list-mock";
import { fetchGatewayModelsPage } from "../../core/services/gateway-service";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import type { RuntimeConfig } from "../../shared/services/runtime-config";

// Mock hooks
const mockListSource = vi.fn();
// The list the server would page through; usePagedList is mocked to search
// it the way the server does and return it as a single page.
const mockUsePagedList = vi.fn();
vi.mock("../../core/hooks/use-paged-list", () => ({
  usePagedList: (fetchPage: unknown, search = "") => {
    mockUsePagedList(fetchPage, search);
    const { allGatewayModels, isLoading, error, refresh } =
      mockListSource() as {
        allGatewayModels: { name: string }[] | null;
        isLoading: boolean;
        error: Error | null;
        refresh: () => void;
      };
    return pagedListState(
      (allGatewayModels ?? []).filter((item: { name: string }) =>
        item.name.toLowerCase().includes(search.toLowerCase()),
      ),
      { isLoading, error, refresh },
    );
  },
}));
vi.mock("../../shared/context/use-runtime-config");

const mockModels = [
  {
    name: "model-1",
    source: "openai",
  },
  {
    name: "model-2",
    source: "anthropic",
  },
];

describe("AiModelsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRuntimeConfig).mockReturnValue({
      basePath: "",
      uiPath: "/",
      provider: "local",
      authenticated: true,
      gen_ai_gateway_enabled: true,
    } as RuntimeConfig);
  });

  it("renders loading state", () => {
    mockListSource.mockReturnValue({
      isLoading: true,
      error: null,
      allGatewayModels: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiModelsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Loading AI models list...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockListSource.mockReturnValue({
      isLoading: false,
      error: new Error("Test error"),
      allGatewayModels: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiModelsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Error: Test error/i)).toBeInTheDocument();
  });

  it("renders models list", () => {
    mockListSource.mockReturnValue({
      isLoading: false,
      error: null,
      allGatewayModels: mockModels,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiModelsPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("model-1")).toBeInTheDocument();
    expect(screen.getByText("model-2")).toBeInTheDocument();
    expect(screen.getByText("openai")).toBeInTheDocument();
  });

  it("filters models by search term", () => {
    mockListSource.mockReturnValue({
      isLoading: false,
      error: null,
      allGatewayModels: mockModels,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiModelsPage />
      </MemoryRouter>,
    );

    const searchInput = screen.getByPlaceholderText("Search AI models...");
    fireEvent.change(searchInput, { target: { value: "model-1" } });
    fireEvent.submit(searchInput);

    expect(mockUsePagedList).toHaveBeenLastCalledWith(
      fetchGatewayModelsPage,
      "model-1",
    );

    expect(screen.getByText("model-1")).toBeInTheDocument();
    expect(screen.queryByText("model-2")).not.toBeInTheDocument();
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
                  <AiModelsPage />
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
        allGatewayModels: [
          { ...mockModels[0], name: "a b@x.com" },
          { ...mockModels[1], name: "team/1" },
        ],
        refresh: vi.fn(),
      });
    });

    it("renders each name as a link to its permissions page", () => {
      renderAtList();
      expect(screen.getByRole("link", { name: "a b@x.com" })).toHaveAttribute(
        "href",
        "/ai-gateway/models/a b@x.com",
      );
      expect(screen.getByRole("link", { name: "team/1" })).toHaveAttribute(
        "href",
        "/ai-gateway/models/team%2F1",
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
        "/ai-gateway/models/team%2F1",
      );
    });

    it("has no Permissions column, Manage permissions button or hidden elements", () => {
      const { container } = renderAtList();
      expect(
        screen.getByRole("columnheader", { name: "Model Name" }),
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
