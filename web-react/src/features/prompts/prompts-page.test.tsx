import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import PromptsPage from "./prompts-page";

const mockUseAllPrompts = vi.fn();
const mockUseSearch = vi.fn();

vi.mock("../../core/hooks/use-all-prompts", () => ({
  useAllPrompts: () => mockUseAllPrompts() as unknown,
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => mockUseSearch() as unknown,
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
  EntityListTable: ({ data }: { data: { name: string }[] }) => (
    <div data-testid="entity-list">
      {data.map((item) => (
        <div key={item.name}>{item.name}</div>
      ))}
    </div>
  ),
}));

vi.mock("../../shared/components/row-action-button", () => ({
  RowActionButton: () => <button>Manage permissions</button>,
}));

describe("PromptsPage", () => {
  beforeEach(() => {
    mockUseSearch.mockReturnValue({
      searchTerm: "",
      submittedTerm: "",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });
    mockUseAllPrompts.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allPrompts: [],
    });
  });

  it("renders correctly with prompts", () => {
    mockUseAllPrompts.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allPrompts: [{ name: "Prompt A" }, { name: "Prompt B" }],
    });

    render(<PromptsPage />);

    expect(screen.getByText("Prompt A")).toBeInTheDocument();
    expect(screen.getByText("Prompt B")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    mockUseAllPrompts.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      allPrompts: [],
    });

    render(<PromptsPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseAllPrompts.mockReturnValue({
      isLoading: false,
      error: new Error("Failed to load"),
      refresh: vi.fn(),
      allPrompts: [],
    });

    render(<PromptsPage />);
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders empty state when no prompts", () => {
    mockUseAllPrompts.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allPrompts: [],
    });

    render(<PromptsPage />);
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
    expect(screen.getByTestId("entity-list")).toBeEmptyDOMElement();
  });

  it("filters prompts based on search", () => {
    mockUseSearch.mockReturnValue({
      searchTerm: "Prompt A",
      submittedTerm: "Prompt A",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    mockUseAllPrompts.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allPrompts: [{ name: "Prompt A" }, { name: "Prompt B" }],
    });

    render(<PromptsPage />);
    expect(screen.getByText("Prompt A")).toBeInTheDocument();
    expect(screen.queryByText("Prompt B")).not.toBeInTheDocument();
  });

  it("renders empty results when search has no matches", () => {
    mockUseSearch.mockReturnValue({
      searchTerm: "NonExistent",
      submittedTerm: "NonExistent",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    mockUseAllPrompts.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allPrompts: [{ name: "Prompt A" }, { name: "Prompt B" }],
    });

    render(<PromptsPage />);
    expect(screen.queryByText("Prompt A")).not.toBeInTheDocument();
    expect(screen.queryByText("Prompt B")).not.toBeInTheDocument();
  });

  it("handles null allPrompts", () => {
    mockUseAllPrompts.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allPrompts: null,
    });

    render(<PromptsPage />);
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
  });
});
