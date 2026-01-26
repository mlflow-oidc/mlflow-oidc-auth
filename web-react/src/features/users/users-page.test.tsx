import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import UsersPage from "./users-page";

const mockUseAllUsers = vi.fn();
const mockUseSearch = vi.fn();

vi.mock("../../core/hooks/use-all-users", () => ({
  useAllUsers: () => mockUseAllUsers() as unknown,
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
  EntityListTable: ({ data }: { data: { id: string; username: string }[] }) => (
    <div data-testid="entity-list">
      {data.map((item) => (
        <div key={item.id}>{item.username}</div>
      ))}
    </div>
  ),
}));

vi.mock("../../shared/components/row-action-button", () => ({
  RowActionButton: () => <button>Manage permissions</button>,
}));

describe("UsersPage", () => {
  beforeEach(() => {
    mockUseSearch.mockReturnValue({
      searchTerm: "",
      submittedTerm: "",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    });
    mockUseAllUsers.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allUsers: [],
    });
  });

  it("renders users list", () => {
    mockUseAllUsers.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      allUsers: ["user1", "user2"],
    });

    render(<UsersPage />);

    expect(screen.getByText("user1")).toBeInTheDocument();
    expect(screen.getByText("user2")).toBeInTheDocument();
  });
});
