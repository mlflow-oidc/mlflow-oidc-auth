import { render, screen, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ModelsPage from "./models-page";
import { MemoryRouter } from "react-router";
import type { ReactNode } from "react";

import type { ModelListItem } from "../../shared/types/entity";
import type { Mock } from "vitest";
import { pagedListState } from "../../tests/paged-list-mock";
import { fetchModelsPage } from "../../core/services/entity-service";

const mockUseAllModels: Mock<
  () => {
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
    allModels: ModelListItem[] | null;
  }
> = vi.fn();

const mockUseSearch: Mock<
  () => {
    searchTerm: string;
    submittedTerm: string;
    handleInputChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    handleSearchSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
    handleClearSearch: () => void;
  }
> = vi.fn();

// The list the server would page through; usePagedList is mocked to search
// it the way the server does and return it as a single page.
const mockUsePagedList = vi.fn();
vi.mock("../../core/hooks/use-paged-list", () => ({
  usePagedList: (fetchPage: unknown, search = "") => {
    mockUsePagedList(fetchPage, search);
    const { allModels, isLoading, error, refresh } = mockUseAllModels();
    return pagedListState(
      (allModels ?? []).filter((item: ModelListItem) =>
        item.name.toLowerCase().includes(search.toLowerCase()),
      ),
      { isLoading, error, refresh },
    );
  },
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => mockUseSearch(),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({
    children,
    title,
  }: {
    children: React.ReactNode;
    title: string;
  }) => (
    <div data-testid="page-container" title={title}>
      {children}
    </div>
  ),
}));

vi.mock("../../shared/components/page/page-status", () => ({
  default: ({
    isLoading,
    error,
  }: {
    isLoading: boolean;
    error: Error | null;
  }) => {
    if (isLoading) return <div>Loading...</div>;
    if (error) return <div>Error</div>;
    return null;
  },
}));

vi.mock("../../shared/components/search-input", () => ({
  SearchInput: () => <div data-testid="search-input" />,
}));

vi.mock("../../shared/components/entity-list-table", () => ({
  EntityListTable: <T extends Record<string, unknown>>({
    data,
    columns,
    getRowHref,
  }: {
    data: T[];
    columns: { header: ReactNode; render: (item: T) => ReactNode }[];
    getRowHref?: (item: T) => string;
  }) => (
    <>
      <div data-testid="entity-list-headers">
        {columns.map((col, i) => (
          // eslint-disable-next-line react-x/no-array-index-key -- test mock; columns are static per render
          <span key={i}>{col.header}</span>
        ))}
      </div>
      <div data-testid="entity-list">
        {data.map((item, rowIndex) => (
          <div
            // eslint-disable-next-line react-x/no-array-index-key -- test mock; rows are static per render
            key={rowIndex}
            data-testid="entity-row"
            data-row-href={getRowHref?.(item)}
          >
            {columns.map((col, i) => (
              // eslint-disable-next-line react-x/no-array-index-key -- test mock; columns are static per render
              <span key={i}>{col.render(item)}</span>
            ))}
          </div>
        ))}
      </div>
    </>
  ),
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <ModelsPage />
    </MemoryRouter>,
  );

describe("ModelsPage", () => {
  beforeEach(() => {
    mockUseSearch.mockReturnValue({
      searchTerm: "",
      submittedTerm: "",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });
    mockUseAllModels.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allModels: [],
    });
  });

  it("renders correctly with models", () => {
    mockUseAllModels.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allModels: [
        { name: "Model A", aliases: "", description: "", tags: {} },
        { name: "Model B", aliases: "", description: "", tags: {} },
      ],
    });

    renderPage();

    expect(screen.getByText("Model A")).toBeInTheDocument();
    expect(screen.getByText("Model B")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    mockUseAllModels.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      allModels: [],
    });

    renderPage();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseAllModels.mockReturnValue({
      isLoading: false,
      error: new Error("Failed to load"),
      refresh: vi.fn(),
      allModels: [],
    });

    renderPage();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders empty state when no models", () => {
    mockUseAllModels.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allModels: [],
    });

    renderPage();
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
    expect(screen.getByTestId("entity-list")).toBeEmptyDOMElement();
  });

  it("filters models based on search", () => {
    mockUseSearch.mockReturnValue({
      searchTerm: "Model A",
      submittedTerm: "Model A",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    mockUseAllModels.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allModels: [
        { name: "Model A", aliases: "", description: "", tags: {} },
        { name: "Model B", aliases: "", description: "", tags: {} },
      ],
    });

    renderPage();
    expect(mockUsePagedList).toHaveBeenCalledWith(fetchModelsPage, "Model A");
    expect(screen.getByText("Model A")).toBeInTheDocument();
    expect(screen.queryByText("Model B")).not.toBeInTheDocument();
  });

  it("renders empty results when search has no matches", () => {
    mockUseSearch.mockReturnValue({
      searchTerm: "NonExistent",
      submittedTerm: "NonExistent",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    mockUseAllModels.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allModels: [
        { name: "Model A", aliases: "", description: "", tags: {} },
        { name: "Model B", aliases: "", description: "", tags: {} },
      ],
    });

    renderPage();
    expect(screen.queryByText("Model A")).not.toBeInTheDocument();
    expect(screen.queryByText("Model B")).not.toBeInTheDocument();
  });

  it("handles null allModels", () => {
    mockUseAllModels.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allModels: null,
    });

    renderPage();
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
  });

  describe("row navigation", () => {
    beforeEach(() => {
      mockUseAllModels.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        allModels: [
          { name: "a b@x.com", aliases: "", description: "", tags: {} },
          { name: "team/1", aliases: "", description: "", tags: {} },
        ],
      });
    });

    it("renders each name as a link to its permissions page", () => {
      renderPage();
      const link0 = screen.getByRole("link", { name: "a b@x.com" });
      expect(link0).toHaveAttribute("href", "/models/a b@x.com");
      const link1 = screen.getByRole("link", { name: "team/1" });
      expect(link1).toHaveAttribute("href", "/models/team%2F1");
    });

    it("makes the whole row navigate to the same destination as the name link", () => {
      renderPage();
      const rows = screen.getAllByTestId("entity-row");
      rows.forEach((row) => {
        const link = within(row).getByRole("link");
        expect(row).toHaveAttribute("data-row-href", link.getAttribute("href"));
      });
    });

    it("has no Permissions column, Manage permissions button or hidden elements", () => {
      const { container } = renderPage();
      const headers = screen.getByTestId("entity-list-headers");
      expect(
        within(headers).queryByText("Permissions"),
      ).not.toBeInTheDocument();
      expect(within(headers).getByText("Name")).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /manage permissions/i }),
      ).not.toBeInTheDocument();
      expect(container.querySelector(".invisible")).toBeNull();
    });

    it("keeps the name link keyboard focusable", () => {
      renderPage();
      const link = screen.getAllByRole("link")[0];
      link.focus();
      expect(document.activeElement).toBe(link);
    });
  });
});
