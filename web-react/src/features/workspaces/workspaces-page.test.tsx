import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import WorkspacesPage from "./workspaces-page";

import type { WorkspaceListItem } from "../../shared/types/entity";
import type { Mock } from "vitest";

const mockUseAllWorkspaces: Mock<
  () => {
    allWorkspaces: WorkspaceListItem[] | null;
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

vi.mock("../../core/hooks/use-all-workspaces", () => ({
  useAllWorkspaces: () => mockUseAllWorkspaces(),
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => mockUseSearch(),
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="page-container" title={title}>
      {children}
    </div>
  ),
}));

vi.mock("../../shared/components/page/page-status", () => ({
  default: ({ isLoading, error }: { isLoading: boolean; error: Error | null }) => {
    if (isLoading) return <div>Loading...</div>;
    if (error) return <div>Error</div>;
    return null;
  },
}));

vi.mock("../../shared/components/search-input", () => ({
  SearchInput: () => <div data-testid="search-input" />,
}));

vi.mock("../../shared/components/entity-list-table", () => ({
  EntityListTable: ({ data, columns }: { data: WorkspaceListItem[]; columns: { render: (item: WorkspaceListItem) => React.ReactNode }[] }) => (
    <div data-testid="entity-list">
      {data.map((item) => (
        <div key={item.name}>
          {columns.map((col, i) => (
            <span key={i}>{col.render(item)}</span>
          ))}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("../../shared/components/row-action-button", () => ({
  RowActionButton: () => <button>Manage members</button>,
}));

describe("WorkspacesPage", () => {
  beforeEach(() => {
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
    });
  });

  it("renders loading state", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: true,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: [],
    });

    render(<WorkspacesPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders workspace list", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: [
        { name: "production", description: "Production workspace", default_artifact_root: "/artifacts/prod" },
        { name: "staging", description: "Staging workspace", default_artifact_root: "/artifacts/staging" },
      ],
    });

    render(<WorkspacesPage />);
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
      allWorkspaces: [
        { name: "production", description: "Production workspace", default_artifact_root: "/artifacts/prod" },
        { name: "staging", description: "Staging workspace", default_artifact_root: "/artifacts/staging" },
      ],
    });

    render(<WorkspacesPage />);
    expect(screen.getByText("production")).toBeInTheDocument();
    expect(screen.queryByText("staging")).not.toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: new Error("Failed to load"),
      refresh: vi.fn(),
      allWorkspaces: [],
    });

    render(<WorkspacesPage />);
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders empty state when no workspaces", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: [],
    });

    render(<WorkspacesPage />);
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
      allWorkspaces: [
        { name: "production", description: "Production workspace", default_artifact_root: "/artifacts/prod" },
        { name: "staging", description: "Staging workspace", default_artifact_root: "/artifacts/staging" },
      ],
    });

    render(<WorkspacesPage />);
    expect(screen.queryByText("production")).not.toBeInTheDocument();
    expect(screen.queryByText("staging")).not.toBeInTheDocument();
  });

  it("handles null allWorkspaces", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: null,
    });

    render(<WorkspacesPage />);
    expect(screen.getByTestId("entity-list")).toBeInTheDocument();
  });

  it("renders description column with dash for empty description", () => {
    mockUseAllWorkspaces.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allWorkspaces: [{ name: "staging", description: "", default_artifact_root: "/artifacts/staging" }],
    });

    render(<WorkspacesPage />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
