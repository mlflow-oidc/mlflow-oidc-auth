import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AiSecretsPage from "./ai-secrets-page";
import { pagedListState } from "../../tests/paged-list-mock";
import { fetchGatewaySecretsPage } from "../../core/services/gateway-service";
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
    const { allGatewaySecrets, isLoading, error, refresh } =
      mockListSource() as {
        allGatewaySecrets: { key: string }[] | null;
        isLoading: boolean;
        error: Error | null;
        refresh: () => void;
      };
    return pagedListState(
      (allGatewaySecrets ?? []).filter((item: { key: string }) =>
        item.key.toLowerCase().includes(search.toLowerCase()),
      ),
      { isLoading, error, refresh },
    );
  },
}));
vi.mock("../../shared/context/use-runtime-config");

const mockSecrets = [
  {
    key: "secret-1",
  },
  {
    key: "secret-2",
  },
];

describe("AiSecretsPage", () => {
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
      allGatewaySecrets: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiSecretsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Loading secrets list...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockListSource.mockReturnValue({
      isLoading: false,
      error: new Error("Test error"),
      allGatewaySecrets: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiSecretsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Error: Test error/i)).toBeInTheDocument();
  });

  it("renders secrets list", () => {
    mockListSource.mockReturnValue({
      isLoading: false,
      error: null,
      allGatewaySecrets: mockSecrets,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiSecretsPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("secret-1")).toBeInTheDocument();
    expect(screen.getByText("secret-2")).toBeInTheDocument();
  });

  it("filters secrets by search term", () => {
    mockListSource.mockReturnValue({
      isLoading: false,
      error: null,
      allGatewaySecrets: mockSecrets,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiSecretsPage />
      </MemoryRouter>,
    );

    const searchInput = screen.getByPlaceholderText("Search secrets...");
    fireEvent.change(searchInput, { target: { value: "secret-1" } });
    fireEvent.submit(searchInput);

    expect(mockUsePagedList).toHaveBeenLastCalledWith(
      fetchGatewaySecretsPage,
      "secret-1",
    );

    expect(screen.getByText("secret-1")).toBeInTheDocument();
    expect(screen.queryByText("secret-2")).not.toBeInTheDocument();
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
                  <AiSecretsPage />
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
        allGatewaySecrets: [{ key: "a b@x.com" }, { key: "team/1" }],
        refresh: vi.fn(),
      });
    });

    it("renders each name as a link to its permissions page", () => {
      renderAtList();
      expect(screen.getByRole("link", { name: "a b@x.com" })).toHaveAttribute(
        "href",
        "/ai-gateway/secrets/a b@x.com",
      );
      expect(screen.getByRole("link", { name: "team/1" })).toHaveAttribute(
        "href",
        "/ai-gateway/secrets/team%2F1",
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
        "/ai-gateway/secrets/team%2F1",
      );
    });

    it("has no Permissions column, Manage permissions button or hidden elements", () => {
      const { container } = renderAtList();
      expect(
        screen.getByRole("columnheader", { name: "Secret Key" }),
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
