import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import GroupsPage from "./groups-page";
import type { GroupDetails } from "../../shared/types/entity";

import type { Mock } from "vitest";

const mockUseAllGroups: Mock<
  () => {
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
    allGroups: string[] | null;
  }
> = vi.fn();

const mockUseAllGroupDetails: Mock<
  () => {
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
    groups: GroupDetails[];
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

const mockUseUser: Mock<() => { currentUser: { is_admin: boolean } | null }> =
  vi.fn();

vi.mock("../../core/hooks/use-all-groups", () => ({
  useAllGroups: () => mockUseAllGroups(),
}));

vi.mock("../../core/hooks/use-all-group-details", () => ({
  useAllGroupDetails: () => mockUseAllGroupDetails(),
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => mockUseSearch(),
}));

vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser(),
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
  EntityListTable: <T extends { id: string }>({
    data,
    columns,
  }: {
    data: T[];
    columns: { render: (item: T) => React.ReactNode }[];
  }) => (
    <div data-testid="entity-list">
      {data.map((item) => (
        <div key={item.id} data-testid={`row-${item.id}`}>
          {columns.map((col, i) => (
            // eslint-disable-next-line react-x/no-array-index-key -- test mock; columns are static per render
            <span key={i}>{col.render(item)}</span>
          ))}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("../../shared/components/row-action-button", () => ({
  RowActionButton: () => <button>Manage permissions</button>,
}));

describe("GroupsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
    mockUseAllGroupDetails.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      groups: [],
    });
    mockUseUser.mockReturnValue({ currentUser: { is_admin: false } });
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

  it("renders loading state", () => {
    mockUseAllGroups.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      allGroups: [],
    });

    render(<GroupsPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseAllGroups.mockReturnValue({
      isLoading: false,
      error: new Error("Failed to load"),
      refresh: vi.fn(),
      allGroups: [],
    });

    render(<GroupsPage />);
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders empty state when no groups", () => {
    mockUseAllGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: [],
    });

    render(<GroupsPage />);
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
    expect(screen.getByTestId("entity-list")).toBeEmptyDOMElement();
  });

  it("filters groups based on search", () => {
    mockUseSearch.mockReturnValue({
      searchTerm: "group1",
      submittedTerm: "group1",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    mockUseAllGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: ["group1", "group2"],
    });

    render(<GroupsPage />);
    expect(screen.getByText("group1")).toBeInTheDocument();
    expect(screen.queryByText("group2")).not.toBeInTheDocument();
  });

  it("renders empty results when search has no matches", () => {
    mockUseSearch.mockReturnValue({
      searchTerm: "NonExistent",
      submittedTerm: "NonExistent",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    mockUseAllGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: ["group1", "group2"],
    });

    render(<GroupsPage />);
    expect(screen.queryByText("group1")).not.toBeInTheDocument();
    expect(screen.queryByText("group2")).not.toBeInTheDocument();
  });

  it("handles null allGroups", () => {
    mockUseAllGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: null,
    });

    render(<GroupsPage />);
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
  });

  describe("admin", () => {
    beforeEach(() => {
      mockUseUser.mockReturnValue({ currentUser: { is_admin: true } });
    });

    const manualGroup: GroupDetails = {
      group_name: "data-team",
      external_id: null,
      member_count: 3,
    };
    const scimGroup: GroupDetails = {
      group_name: "platform",
      external_id: "okta-123",
      member_count: 7,
    };

    it("does not call the legacy string-list hook", () => {
      mockUseAllGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [manualGroup],
      });

      render(<GroupsPage />);
      expect(mockUseAllGroups).not.toHaveBeenCalled();
    });

    it("renders member count and Manual source badge", () => {
      mockUseAllGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [manualGroup],
      });

      render(<GroupsPage />);
      expect(screen.getByText("data-team")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("Manual")).toBeInTheDocument();
    });

    it("renders SCIM source badge when external_id is set", () => {
      mockUseAllGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [scimGroup],
      });

      render(<GroupsPage />);
      expect(screen.getByText("platform")).toBeInTheDocument();
      expect(screen.getByText("7")).toBeInTheDocument();
      expect(screen.getByText("SCIM")).toBeInTheDocument();
    });

    it("filters groups based on search", () => {
      mockUseSearch.mockReturnValue({
        searchTerm: "data",
        submittedTerm: "data",
        handleInputChange: vi.fn(),
        handleSearchSubmit: vi.fn(),
        handleClearSearch: vi.fn(),
      });
      mockUseAllGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [manualGroup, scimGroup],
      });

      render(<GroupsPage />);
      expect(screen.getByText("data-team")).toBeInTheDocument();
      expect(screen.queryByText("platform")).not.toBeInTheDocument();
    });
  });
});
