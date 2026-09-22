import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import UsersPage from "./users-page";
import * as userService from "../../core/services/user-service";
import type { UserDetails } from "../../shared/types/user";

const mockUseAllUsers = vi.fn();
const mockUseAllUserDetails = vi.fn();
const mockUseSearch = vi.fn();
const mockUseUser = vi.fn();
const mockShowToast = vi.fn();

vi.mock("../../core/hooks/use-all-users", () => ({
  useAllUsers: () => mockUseAllUsers() as unknown,
}));

vi.mock("../../core/hooks/use-all-user-details", () => ({
  useAllUserDetails: (...args: unknown[]) =>
    mockUseAllUserDetails(...args) as unknown,
}));

vi.mock("../../core/hooks/use-search", () => ({
  useSearch: () => mockUseSearch() as unknown,
}));

vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => mockUseUser() as unknown,
}));

vi.mock("../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

vi.mock("../../core/services/user-service", async () => {
  const actual = await vi.importActual<typeof userService>(
    "../../core/services/user-service",
  );
  return {
    ...actual,
    setUserActive: vi.fn(),
  };
});

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
    columns: { header: React.ReactNode; render: (item: T) => React.ReactNode }[];
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

vi.mock("../../shared/components/icon-button", () => ({
  IconButton: ({
    title,
    onClick,
    disabled,
  }: {
    title: string;
    onClick: () => void;
    disabled?: boolean;
  }) => (
    <button
      data-testid={`icon-btn-${title}`}
      onClick={onClick}
      disabled={disabled}
    >
      {title}
    </button>
  ),
}));

const adminUser: UserDetails = {
  username: "alice@example.com",
  display_name: "Alice",
  is_admin: true,
  is_service_account: false,
  active: true,
  managed_by: "manual",
};

const scimUser: UserDetails = {
  username: "bob@example.com",
  display_name: "Bob",
  is_admin: false,
  is_service_account: false,
  active: true,
  managed_by: "scim",
};

const inactiveUser: UserDetails = {
  username: "carol@example.com",
  display_name: "Carol",
  is_admin: false,
  is_service_account: false,
  active: false,
  managed_by: "oidc:okta-prod",
};

describe("UsersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
    mockUseAllUserDetails.mockReturnValue({
      isLoading: false,
      error: null,
      refresh: vi.fn(),
      updateLocalUser: vi.fn(),
      users: [],
    });
  });

  describe("non-admin", () => {
    beforeEach(() => {
      mockUseUser.mockReturnValue({ currentUser: { is_admin: false } });
    });

    it("renders the legacy username-only view", () => {
      mockUseAllUsers.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        allUsers: ["user1", "user2"],
      });

      render(<UsersPage />);

      expect(screen.getByText("user1")).toBeInTheDocument();
      expect(screen.getByText("user2")).toBeInTheDocument();
      // No lifecycle columns for non-admins.
      expect(screen.queryByText("Active")).not.toBeInTheDocument();
      expect(mockUseAllUserDetails).not.toHaveBeenCalled();
    });
  });

  describe("admin", () => {
    beforeEach(() => {
      mockUseUser.mockReturnValue({ currentUser: { is_admin: true } });
    });

    it("renders lifecycle badges and the deactivate action", () => {
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser: vi.fn(),
        users: [adminUser],
      });

      render(<UsersPage />);

      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
      expect(screen.getByText("Alice")).toBeInTheDocument();
      expect(screen.getByText("Active")).toBeInTheDocument();
      expect(screen.getByText("Manual")).toBeInTheDocument();
      expect(
        screen.getByTestId("icon-btn-Deactivate user"),
      ).toBeInTheDocument();
    });

    it("shows a reactivate action for an inactive user", () => {
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser: vi.fn(),
        users: [inactiveUser],
      });

      render(<UsersPage />);

      expect(screen.getByText("Inactive")).toBeInTheDocument();
      expect(screen.getByText("OIDC · okta-prod")).toBeInTheDocument();
      expect(
        screen.getByTestId("icon-btn-Reactivate user"),
      ).toBeInTheDocument();
    });

    it("deactivate confirm calls the service and updates local state", async () => {
      const updateLocalUser = vi.fn();
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser,
        users: [adminUser],
      });
      const updated = { ...adminUser, active: false };
      vi.mocked(userService.setUserActive).mockResolvedValue(updated);

      render(<UsersPage />);

      fireEvent.click(screen.getByTestId("icon-btn-Deactivate user"));

      // Modal is open; confirm the deactivation.
      const dialogButtons = screen.getAllByText("Deactivate");
      fireEvent.click(dialogButtons[dialogButtons.length - 1]);

      await waitFor(() => {
        expect(userService.setUserActive).toHaveBeenCalledWith(
          "alice@example.com",
          false,
          false,
        );
        expect(updateLocalUser).toHaveBeenCalledWith(
          "alice@example.com",
          updated,
        );
      });
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.stringContaining("deactivated"),
        "success",
      );
    });

    it("shows the server message in a toast on a 409 refusal", async () => {
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser: vi.fn(),
        users: [adminUser],
      });
      const error = new Error(
        'HTTP 409: {"detail": "Refusing to remove the last active administrator"}',
      );
      vi.mocked(userService.setUserActive).mockRejectedValue(error);

      render(<UsersPage />);

      fireEvent.click(screen.getByTestId("icon-btn-Deactivate user"));
      const dialogButtons = screen.getAllByText("Deactivate");
      fireEvent.click(dialogButtons[dialogButtons.length - 1]);

      await waitFor(() => {
        expect(mockShowToast).toHaveBeenCalledWith(
          "Refusing to remove the last active administrator",
          "error",
        );
      });
    });

    it("shows the ownership override switch for a SCIM-managed user and passes admin_override:true when toggled", async () => {
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser: vi.fn(),
        users: [scimUser],
      });
      vi.mocked(userService.setUserActive).mockResolvedValue({
        ...scimUser,
        active: false,
      });

      render(<UsersPage />);

      fireEvent.click(screen.getByTestId("icon-btn-Deactivate user"));

      expect(screen.getByText("Override ownership guard")).toBeInTheDocument();

      const overrideLabel = screen
        .getByText("Override ownership guard")
        .closest("label");
      expect(overrideLabel).not.toBeNull();
      fireEvent.click(within(overrideLabel as HTMLElement).getByRole("switch"));

      const dialogButtons = screen.getAllByText("Deactivate");
      fireEvent.click(dialogButtons[dialogButtons.length - 1]);

      await waitFor(() => {
        expect(userService.setUserActive).toHaveBeenCalledWith(
          "bob@example.com",
          false,
          true,
        );
      });
    });

    it("hides inactive users when the Show inactive toggle is off", () => {
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser: vi.fn(),
        users: [adminUser, inactiveUser],
      });

      render(<UsersPage />);

      expect(screen.getByText("carol@example.com")).toBeInTheDocument();

      const showInactiveLabel = screen
        .getByText("Show inactive")
        .closest("label");
      fireEvent.click(
        within(showInactiveLabel as HTMLElement).getByRole("switch"),
      );

      expect(screen.queryByText("carol@example.com")).not.toBeInTheDocument();
    });
  });
});
