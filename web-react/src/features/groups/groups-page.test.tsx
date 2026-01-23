import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import GroupsPage from "./groups-page";

const mockUseAllGroups = vi.fn();
const mockUseSearch = vi.fn();

vi.mock("../../core/hooks/use-all-groups", () => ({
  useAllGroups: () => mockUseAllGroups(),
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
        <div key={item.id}>{item.groupName}</div>
      ))}
    </div>
  ),
}));

vi.mock("../../shared/components/row-action-button", () => ({
  RowActionButton: () => <button>Manage permissions</button>,
}));

describe("GroupsPage", () => {
  beforeEach(() => {
    mockUseSearch.mockReturnValue({
      searchTerm: "",
      submittedTerm: "",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });
    mockUseAllGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: [],
    });
  });

  it("renders correctly with groups", () => {
    mockUseAllGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: ["group1", "group2"],
    });

    render(<GroupsPage />);

    expect(screen.getByText("group1")).toBeInTheDocument();
    expect(screen.getByText("group2")).toBeInTheDocument();
  });
});
