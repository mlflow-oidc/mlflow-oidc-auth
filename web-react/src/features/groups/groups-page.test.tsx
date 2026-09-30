import React from "react";
import { render, screen, fireEvent, act, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, it, expect, vi, beforeEach } from "vitest";
import GroupsPage from "./groups-page";
import type { GroupDetails } from "../../shared/types/entity";
import {
  fetchGroupDetailsPage,
  fetchGroupsPage,
} from "../../core/services/entity-service";
import { pagedListState } from "../../tests/paged-list-mock";

import type { Mock } from "vitest";

const mockLegacyGroups: Mock<
  () => {
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
    allGroups: string[] | null;
  }
> = vi.fn();

const mockGroupDetails: Mock<
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

// The page pages both lists through usePagedList; the mock routes by fetcher
// and applies the search the way the server does.
const mockUsePagedList = vi.fn((fetchPage: unknown, search: string = "") => {
  const term = search.toLowerCase();
  if (fetchPage === fetchGroupsPage) {
    const { allGroups, ...rest } = mockLegacyGroups();
    return pagedListState(
      (allGroups ?? []).filter((g) => g.toLowerCase().includes(term)),
      rest,
    );
  }
  const { groups, ...rest } = mockGroupDetails();
  return pagedListState(
    groups.filter((g) => g.group_name.toLowerCase().includes(term)),
    rest,
  );
});

vi.mock("../../core/hooks/use-paged-list", () => ({
  usePagedList: (fetchPage: unknown, search?: string) =>
    mockUsePagedList(fetchPage, search),
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
  EntityListTable: <T extends Record<string, unknown>>({
    data,
    columns,
    getRowHref,
  }: {
    data: T[];
    columns: {
      header: React.ReactNode;
      render: (item: T) => React.ReactNode;
    }[];
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

const mockOnCreated = { current: (() => {}) as () => void };

vi.mock("./components/create-group-modal", () => ({
  CreateGroupModal: ({
    isOpen,
    onCreated,
  }: {
    isOpen: boolean;
    onClose: () => void;
    onCreated: () => void;
  }) => {
    mockOnCreated.current = onCreated;
    return isOpen ? <div data-testid="create-group-modal" /> : null;
  },
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <GroupsPage />
    </MemoryRouter>,
  );

const expectRowNavigation = (
  container: HTMLElement,
  expected: [name: string, href: string][],
) => {
  expected.forEach(([name, href]) => {
    const link = screen.getByRole("link", { name });
    expect(link).toHaveAttribute("href", href);
    expect(link.closest('[data-testid="entity-row"]')).toHaveAttribute(
      "data-row-href",
      href,
    );
  });
  const headers = screen.getByTestId("entity-list-headers");
  expect(within(headers).queryByText("Permissions")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /manage permissions/i }),
  ).not.toBeInTheDocument();
  expect(container.querySelector(".invisible")).toBeNull();
};

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
    mockLegacyGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: [],
    });
    mockGroupDetails.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      groups: [],
    });
    mockUseUser.mockReturnValue({ currentUser: { is_admin: false } });
  });

  it("renders correctly with groups", () => {
    mockLegacyGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: ["group1", "group2"],
    });

    renderPage();

    expect(screen.getByText("group1")).toBeInTheDocument();
    expect(screen.getByText("group2")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    mockLegacyGroups.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      allGroups: [],
    });

    renderPage();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockLegacyGroups.mockReturnValue({
      isLoading: false,
      error: new Error("Failed to load"),
      refresh: vi.fn(),
      allGroups: [],
    });

    renderPage();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders empty state when no groups", () => {
    mockLegacyGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: [],
    });

    renderPage();
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

    mockLegacyGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: ["group1", "group2"],
    });

    renderPage();
    expect(mockUsePagedList).toHaveBeenCalledWith(fetchGroupsPage, "group1");
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

    mockLegacyGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: ["group1", "group2"],
    });

    renderPage();
    expect(screen.queryByText("group1")).not.toBeInTheDocument();
    expect(screen.queryByText("group2")).not.toBeInTheDocument();
  });

  it("handles null allGroups", () => {
    mockLegacyGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: null,
    });

    renderPage();
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
  });

  it("links each group name to its permissions page (non-admin)", () => {
    mockLegacyGroups.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allGroups: ["a b@x.com", "team/1"],
    });

    const { container } = renderPage();
    expectRowNavigation(container, [
      ["a b@x.com", "/groups/a b@x.com/experiments"],
      ["team/1", "/groups/team%2F1/experiments"],
    ]);

    const link = screen.getByRole("link", { name: "team/1" });
    link.focus();
    expect(document.activeElement).toBe(link);
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
      mockGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [manualGroup],
      });

      renderPage();
      expect(mockUsePagedList).not.toHaveBeenCalledWith(
        fetchGroupsPage,
        expect.anything(),
      );
      expect(mockUsePagedList).toHaveBeenCalledWith(fetchGroupDetailsPage, "");
    });

    it("renders member count and Manual source badge", () => {
      mockGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [manualGroup],
      });

      renderPage();
      expect(screen.getByText("data-team")).toBeInTheDocument();
      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getByText("Manual")).toBeInTheDocument();
    });

    it("renders SCIM source badge when external_id is set", () => {
      mockGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [scimGroup],
      });

      renderPage();
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
      mockGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [manualGroup, scimGroup],
      });

      renderPage();
      expect(mockUsePagedList).toHaveBeenCalledWith(
        fetchGroupDetailsPage,
        "data",
      );
      expect(screen.getByText("data-team")).toBeInTheDocument();
      expect(screen.queryByText("platform")).not.toBeInTheDocument();
    });

    it("opens the create-group modal from the Create group button", () => {
      mockGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [manualGroup],
      });

      renderPage();

      expect(
        screen.queryByTestId("create-group-modal"),
      ).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "+ Create group" }));
      expect(screen.getByTestId("create-group-modal")).toBeInTheDocument();
    });

    it("refreshes the group list when a group is created", () => {
      const refresh = vi.fn();
      mockGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh,
        groups: [manualGroup],
      });

      renderPage();
      fireEvent.click(screen.getByRole("button", { name: "+ Create group" }));
      act(() => {
        mockOnCreated.current();
      });

      expect(refresh).toHaveBeenCalled();
    });

    it("links each group name to its permissions page", () => {
      mockGroupDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        groups: [
          { ...manualGroup, group_name: "a b@x.com" },
          { ...scimGroup, group_name: "team/1" },
        ],
      });

      const { container } = renderPage();
      expectRowNavigation(container, [
        ["a b@x.com", "/groups/a b@x.com/experiments"],
        ["team/1", "/groups/team%2F1/experiments"],
      ]);
      expect(
        within(screen.getByTestId("entity-list-headers")).getByText("Source"),
      ).toBeInTheDocument();
    });
  });
});
