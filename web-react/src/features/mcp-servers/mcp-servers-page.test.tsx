import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router";
import McpServersPage from "./mcp-servers-page";
import { pagedListState } from "../../tests/paged-list-mock";
import { fetchMcpServersPage } from "../../core/services/mcp-server-service";
import type { McpServerListItem } from "../../shared/types/entity";

const mockListSource = vi.fn();
const mockUsePagedList = vi.fn();
vi.mock("../../core/hooks/use-paged-list", () => ({
  usePagedList: (fetchPage: unknown, search = "") => {
    mockUsePagedList(fetchPage, search);
    const { servers, isLoading, error, refresh } = mockListSource() as {
      servers: McpServerListItem[];
      isLoading: boolean;
      error: Error | null;
      refresh: () => void;
    };
    return pagedListState(
      servers.filter((s) =>
        s.name.toLowerCase().includes(search.toLowerCase()),
      ),
      { isLoading, error, refresh },
    );
  },
}));

const servers: McpServerListItem[] = [
  {
    name: "com.example/weather",
    display_name: "Weather",
    latest_version: "1.0.0",
  },
  { name: "org.acme/search", display_name: null, latest_version: null },
];

const renderPage = () =>
  render(
    <MemoryRouter>
      <McpServersPage />
    </MemoryRouter>,
  );

describe("McpServersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state", () => {
    mockListSource.mockReturnValue({
      servers: [],
      isLoading: true,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText("Loading MCP servers...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockListSource.mockReturnValue({
      servers: [],
      isLoading: false,
      error: new Error("boom"),
      refresh: vi.fn(),
    });
    renderPage();
    expect(screen.getByText(/Error: boom/i)).toBeInTheDocument();
  });

  it("links each server to its permissions page, keeping the slash in one segment", () => {
    mockListSource.mockReturnValue({
      servers,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();

    expect(
      screen.getByRole("link", { name: "com.example/weather" }),
    ).toHaveAttribute("href", "/mcp-servers/com.example%2Fweather");
    expect(screen.getByText("Weather")).toBeInTheDocument();
    expect(screen.getByText("1.0.0")).toBeInTheDocument();
  });

  it("searches through the paged fetcher", () => {
    mockListSource.mockReturnValue({
      servers,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    renderPage();

    const input = screen.getByPlaceholderText("Search MCP servers...");
    fireEvent.change(input, { target: { value: "acme" } });
    fireEvent.submit(input);

    expect(mockUsePagedList).toHaveBeenLastCalledWith(
      fetchMcpServersPage,
      "acme",
    );
    expect(screen.getByText("org.acme/search")).toBeInTheDocument();
    expect(screen.queryByText("com.example/weather")).not.toBeInTheDocument();
  });
});
