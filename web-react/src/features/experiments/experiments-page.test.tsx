import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ExperimentsPage from "./experiments-page";

const mockUseAllExperiments = vi.fn();
const mockUseSearch = vi.fn();

vi.mock("../../core/hooks/use-all-experiments", () => ({
  useAllExperiments: () => mockUseAllExperiments(),
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => mockUseSearch(),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="page-container" title={title}>{children}</div>
  ),
}));

vi.mock("../../shared/components/page/page-status", () => ({
  default: ({ isLoading, error }: any) => {
    if (isLoading) return <div>Loading...</div>;
    if (error) return <div>Error</div>;
    return null;
  },
}));

vi.mock("../../shared/components/search-input", () => ({
  SearchInput: () => <div data-testid="search-input" />,
}));

vi.mock("../../shared/components/entity-list-table", () => ({
  EntityListTable: ({ data }: any) => (
    <div data-testid="entity-list">
      {data.map((item: any) => (
        <div key={item.id}>{item.name}</div>
      ))}
    </div>
  ),
}));

vi.mock("../../shared/components/row-action-button", () => ({
  RowActionButton: () => <button>Manage permissions</button>,
}));

describe("ExperimentsPage", () => {
  beforeEach(() => {
    mockUseSearch.mockReturnValue({
      searchTerm: "",
      submittedTerm: "",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });
    mockUseAllExperiments.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allExperiments: [],
    });
  });

  it("renders loading state", () => {
    mockUseAllExperiments.mockReturnValue({
        isLoading: true,
        error: null,
        refresh: vi.fn(),
        allExperiments: [],
    });

    render(<ExperimentsPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders experiment list", () => {
     mockUseAllExperiments.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        allExperiments: [
            { id: "1", name: "Exp 1" },
            { id: "2", name: "Exp 2" },
        ],
    });

    render(<ExperimentsPage />);
    expect(screen.getByText("Exp 1")).toBeInTheDocument();
    expect(screen.getByText("Exp 2")).toBeInTheDocument();
  });
  
  it("filters experiments based on search", () => {
    mockUseSearch.mockReturnValue({
      searchTerm: "Exp 1",
      submittedTerm: "Exp 1",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });
    
    mockUseAllExperiments.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        allExperiments: [
            { id: "1", name: "Exp 1" },
            { id: "2", name: "Exp 2" },
        ],
    });

    render(<ExperimentsPage />);
    expect(screen.getByText("Exp 1")).toBeInTheDocument();
    expect(screen.queryByText("Exp 2")).not.toBeInTheDocument();
  });
});
