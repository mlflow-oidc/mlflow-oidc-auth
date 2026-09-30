import React from "react";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, it, expect, vi, beforeEach } from "vitest";
import WorkspacesPage from "./workspaces-page";

import type {
  WorkspaceListItem,
  WorkspaceMemberCounts,
} from "../../shared/types/entity";
import type { Mock } from "vitest";

const mockNavigate = vi.fn();

vi.mock("react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router")>()),
  Navigate: (props: { to: string }) => {
    mockNavigate(props.to);
    return <div data-testid="navigate" data-to={props.to} />;
  },
}));

const mockUseRuntimeConfig: Mock<() => { workspaces_enabled: boolean }> =
  vi.fn();

vi.mock("../../shared/context/use-runtime-config", () => ({
  useRuntimeConfig: () => mockUseRuntimeConfig(),
}));

const mockUseAllWorkspaces: Mock<
  () => {
    allWorkspaces: WorkspaceListItem[] | null;
    memberCounts: Record<string, WorkspaceMemberCounts> | null;
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
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

const mockUseUser: Mock<
  () => {
    currentUser: { is_admin: boolean } | null;
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
  }
> = vi.fn();

const mockShowToast = vi.fn();

vi.mock("../../core/hooks/use-all-workspaces", () => ({
  useAllWorkspaces: () => mockUseAllWorkspaces(),
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => mockUseSearch(),
}));

vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser(),
}));

vi.mock("../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

vi.mock("../../core/services/workspace-service", () => ({
  deleteWorkspace: vi.fn(),
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

vi.mock("../../shared/components/icon-button", () => ({
  IconButton: ({ title, muted }: { title: string; muted?: boolean }) => (
    <button
      data-testid={`icon-btn-${title}`}
      data-muted={muted ? "true" : "false"}
    >
      {title}
    </button>
  ),
}));

vi.mock("./components/create-workspace-modal", () => ({
  CreateWorkspaceModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="create-workspace-modal" /> : null,
}));

vi.mock("./components/edit-workspace-modal", () => ({
  EditWorkspaceModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="edit-workspace-modal" /> : null,
}));

vi.mock("./components/delete-workspace-modal", () => ({
  DeleteWorkspaceModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="delete-workspace-modal" /> : null,
}));

const defaultWorkspaces: WorkspaceListItem[] = [
  {
    name: "production",
    description: "Production workspace",
    default_artifact_root: "/artifacts/prod",
  },
  {
    name: "staging",
    description: "Staging workspace",
    default_artifact_root: "/artifacts/staging",
  },
];

const defaultMemberCounts: Record<string, WorkspaceMemberCounts> = {
  production: { users: 5, groups: 2 },
  staging: { users: 3, groups: 1 },
};

const renderPage = () =>
  render(
    <MemoryRouter>
      <WorkspacesPage />
    </MemoryRouter>,
  );

describe("WorkspacesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRuntimeConfig.mockReturnValue({ workspaces_enabled: true });
    mockUseSearch.mockReturnValue({
      searchTerm: "",
      submittedTerm: "",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: [],
      memberCounts: null,
    });
    mockUseUser.mockReturnValue({
      currentUser: { is_admin: false },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
  });

  it("renders loading state", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: [],
      memberCounts: null,
    });

    renderPage();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders workspace list", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: defaultWorkspaces,
      memberCounts: null,
    });

    renderPage();
    expect(screen.getByText("production")).toBeInTheDocument();
    expect(screen.getByText("staging")).toBeInTheDocument();
  });

  it("filters workspaces based on search", () => {
    mockUseSearch.mockReturnValue({
      searchTerm: "prod",
      submittedTerm: "prod",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: defaultWorkspaces,
      memberCounts: null,
    });

    renderPage();
    expect(screen.getByText("production")).toBeInTheDocument();
    expect(screen.queryByText("staging")).not.toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: new Error("Failed to load"),
      refresh: vi.fn(),
      allWorkspaces: [],
      memberCounts: null,
    });

    renderPage();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders empty state when no workspaces", () => {
    renderPage();
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
    expect(screen.getByTestId("entity-list")).toBeEmptyDOMElement();
  });

  it("renders empty results when search has no matches", () => {
    mockUseSearch.mockReturnValue({
      searchTerm: "NonExistent",
      submittedTerm: "NonExistent",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });

    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: defaultWorkspaces,
      memberCounts: null,
    });

    renderPage();
    expect(screen.queryByText("production")).not.toBeInTheDocument();
    expect(screen.queryByText("staging")).not.toBeInTheDocument();
  });

  it("handles null allWorkspaces", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: null,
      memberCounts: null,
    });

    renderPage();
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
  });

  it("renders description column with dash for empty description", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: [
        {
          name: "staging",
          description: "",
          default_artifact_root: "/artifacts/staging",
        },
      ],
      memberCounts: null,
    });

    renderPage();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders Create Workspace button when admin", () => {
    mockUseUser.mockReturnValue({
      currentUser: { is_admin: true },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    renderPage();
    expect(screen.getByText("Create Workspace")).toBeInTheDocument();
  });

  it("does not render Create Workspace button when not admin", () => {
    mockUseUser.mockReturnValue({
      currentUser: { is_admin: false },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    renderPage();
    expect(screen.queryByText("Create Workspace")).not.toBeInTheDocument();
  });

  it("renders member counts in workspace list", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: defaultWorkspaces,
      memberCounts: defaultMemberCounts,
    });

    renderPage();
    expect(screen.getByText(/5 users,/)).toBeInTheDocument();
    expect(screen.getByText(/2 groups/)).toBeInTheDocument();
    expect(screen.getByText(/3 users,/)).toBeInTheDocument();
    expect(screen.getByText(/1 groups/)).toBeInTheDocument();
  });

  it("renders loading indicator for member counts when not yet loaded", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: defaultWorkspaces,
      memberCounts: null,
    });

    renderPage();
    expect(screen.getAllByText(/… users,/).length).toBe(2);
  });

  it("renders edit and delete icons for admin", () => {
    mockUseUser.mockReturnValue({
      currentUser: { is_admin: true },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: defaultWorkspaces,
      memberCounts: null,
    });

    renderPage();
    expect(screen.getAllByTestId("icon-btn-Edit workspace").length).toBe(2);
    expect(screen.getAllByTestId("icon-btn-Delete workspace").length).toBe(2);
  });

  it("does not render edit and delete icons for non-admin", () => {
    mockUseUser.mockReturnValue({
      currentUser: { is_admin: false },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: defaultWorkspaces,
      memberCounts: null,
    });

    renderPage();
    expect(
      screen.queryByTestId("icon-btn-Edit workspace"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("icon-btn-Delete workspace"),
    ).not.toBeInTheDocument();
  });

  it("redirects to home when workspaces are disabled", () => {
    mockUseRuntimeConfig.mockReturnValue({ workspaces_enabled: false });

    renderPage();
    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/");
  });

  describe("row navigation", () => {
    const setAdmin = (isAdmin: boolean) =>
      mockUseUser.mockReturnValue({
        currentUser: { is_admin: isAdmin },
        isLoading: false,
        error: null,
        refresh: vi.fn(),
      });

    beforeEach(() => {
      mockUseAllWorkspaces.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        allWorkspaces: [
          { ...defaultWorkspaces[0], name: "a b@x.com" },
          { ...defaultWorkspaces[1], name: "team/1" },
        ],
        memberCounts: null,
      });
    });

    it("links each workspace name to its members page", () => {
      renderPage();

      expect(screen.getByRole("link", { name: "a b@x.com" })).toHaveAttribute(
        "href",
        "/workspaces/a b@x.com",
      );
      expect(screen.getByRole("link", { name: "team/1" })).toHaveAttribute(
        "href",
        "/workspaces/team%2F1",
      );
      screen.getAllByTestId("entity-row").forEach((row) => {
        const link = within(row).getByRole("link");
        expect(row).toHaveAttribute("data-row-href", link.getAttribute("href"));
      });
    });

    it("has no Manage members button or hidden elements", () => {
      setAdmin(true);
      const { container } = renderPage();

      expect(
        screen.queryByRole("button", { name: /manage members/i }),
      ).not.toBeInTheDocument();
      expect(container.querySelector(".invisible")).toBeNull();
    });

    it("keeps admin edit/delete actions visible but muted", () => {
      setAdmin(true);
      renderPage();

      const headers = screen.getByTestId("entity-list-headers");
      expect(within(headers).getByText("Actions")).toBeInTheDocument();
      [
        ...screen.getAllByTestId("icon-btn-Edit workspace"),
        ...screen.getAllByTestId("icon-btn-Delete workspace"),
      ].forEach((button) => {
        expect(button).toHaveAttribute("data-muted", "true");
        expect(button.closest(".invisible")).toBeNull();
      });
    });

    it("omits the empty Actions column for non-admins", () => {
      setAdmin(false);
      renderPage();

      const headers = screen.getByTestId("entity-list-headers");
      expect(within(headers).queryByText("Actions")).not.toBeInTheDocument();
      expect(within(headers).getByText("Workspace Name")).toBeInTheDocument();
    });

    it("keeps the name link keyboard focusable", () => {
      renderPage();
      const link = screen.getByRole("link", { name: "team/1" });
      link.focus();
      expect(document.activeElement).toBe(link);
    });
  });
});
