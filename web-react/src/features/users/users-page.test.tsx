import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import UsersPage from "./users-page";
import * as userService from "../../core/services/user-service";
import type { UserDetails } from "../../shared/types/user";
import { pagedListState } from "../../tests/paged-list-mock";

const mockLegacyUsers = vi.fn();
const mockUseAllUserDetails = vi.fn();
const mockUseSearch = vi.fn();
const mockUseUser = vi.fn();
const mockShowToast = vi.fn();

// The non-admin view pages usernames through usePagedList; the mock serves
// mockLegacyUsers' list and applies the search the way the server does.
const mockUsePagedList = vi.fn((_fetchPage: unknown, search: string = "") => {
  const { allUsers, ...rest } = mockLegacyUsers() as {
    allUsers: string[] | null;
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
  };
  return pagedListState(
    (allUsers ?? []).filter((u) =>
      u.toLowerCase().includes(search.toLowerCase()),
    ),
    rest,
  );
});

vi.mock("../../core/hooks/use-paged-list", () => ({
  usePagedList: (fetchPage: unknown, search?: string) =>
    mockUsePagedList(fetchPage, search),
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

vi.mock("./components/user-sessions-modal", () => ({
  UserSessionsModal: ({
    username,
    onClose,
  }: {
    username: string | null;
    onClose: () => void;
  }) =>
    username ? (
      <div data-testid="sessions-modal">
        {username}
        <button onClick={onClose}>close sessions</button>
      </div>
    ) : null,
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

const inactiveScimUser: UserDetails = {
  username: "dave@example.com",
  display_name: "Dave",
  is_admin: false,
  is_service_account: false,
  active: false,
  managed_by: "scim",
};

function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/users"]}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <UsersPage />
              <LocationDisplay />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );

/** The table row that holds the given username's link. */
const getRow = (username: string): HTMLElement => {
  const row = screen
    .getByRole("link", { name: username })
    .closest<HTMLElement>('[role="row"]');
  if (!row) throw new Error(`no row for ${username}`);
  return row;
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
    mockLegacyUsers.mockReturnValue({
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
      mockLegacyUsers.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        allUsers: ["user1", "user2"],
      });

      renderPage();

      expect(screen.getByText("user1")).toBeInTheDocument();
      expect(screen.getByText("user2")).toBeInTheDocument();
      // No lifecycle columns for non-admins.
      expect(screen.queryByText("Active")).not.toBeInTheDocument();
      expect(mockUseAllUserDetails).not.toHaveBeenCalled();
      expect(mockUsePagedList).toHaveBeenCalledWith(
        userService.fetchUsersPage,
        "",
      );
    });

    it("links each username to its permissions page and navigates on row click", () => {
      mockLegacyUsers.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        allUsers: ["a b@x.com", "team/1"],
      });

      const { container } = renderPage();

      expect(screen.getByRole("link", { name: "a b@x.com" })).toHaveAttribute(
        "href",
        "/users/a b@x.com/experiments",
      );
      expect(screen.getByRole("link", { name: "team/1" })).toHaveAttribute(
        "href",
        "/users/team%2F1/experiments",
      );
      expect(
        screen.queryByRole("columnheader", { name: "Permissions" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /manage permissions/i }),
      ).not.toBeInTheDocument();
      expect(container.querySelector(".invisible")).toBeNull();

      const link = screen.getByRole("link", { name: "team/1" });
      link.focus();
      expect(document.activeElement).toBe(link);

      fireEvent.click(within(getRow("team/1")).getAllByRole("cell")[0]);
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/users/team%2F1/experiments",
      );
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

      renderPage();

      expect(screen.getByText("alice@example.com")).toBeInTheDocument();
      expect(screen.getByText("Alice")).toBeInTheDocument();
      expect(screen.getByText("Active")).toBeInTheDocument();
      expect(screen.getByText("Manual")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Deactivate user" }),
      ).toBeInTheDocument();
    });

    it("opens the sessions modal for a user", () => {
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser: vi.fn(),
        users: [adminUser, scimUser],
      });

      renderPage();
      expect(screen.queryByTestId("sessions-modal")).not.toBeInTheDocument();

      const row = getRow(scimUser.username);
      fireEvent.click(within(row).getByRole("button", { name: "Sessions" }));
      expect(screen.getByTestId("sessions-modal")).toHaveTextContent(
        scimUser.username,
      );

      fireEvent.click(screen.getByText("close sessions"));
      expect(screen.queryByTestId("sessions-modal")).not.toBeInTheDocument();
    });

    it("shows a reactivate action for an inactive user", () => {
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser: vi.fn(),
        users: [inactiveUser],
      });

      renderPage();

      expect(screen.getByText("Inactive")).toBeInTheDocument();
      expect(screen.getByText("OIDC · okta-prod")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Reactivate user" }),
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

      renderPage();

      fireEvent.click(screen.getByRole("button", { name: "Deactivate user" }));

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

      renderPage();

      fireEvent.click(screen.getByRole("button", { name: "Deactivate user" }));
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

      renderPage();

      fireEvent.click(screen.getByRole("button", { name: "Deactivate user" }));

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

    it("reactivate opens a confirm modal and calls the service on confirm", async () => {
      const updateLocalUser = vi.fn();
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser,
        users: [inactiveUser],
      });
      const updated = { ...inactiveUser, active: true };
      vi.mocked(userService.setUserActive).mockResolvedValue(updated);

      renderPage();

      fireEvent.click(screen.getByRole("button", { name: "Reactivate user" }));

      // The confirm modal, not an immediate call — otherwise there is no way to opt into the
      // ownership override for a directory-managed user.
      expect(userService.setUserActive).not.toHaveBeenCalled();
      expect(screen.getByText("Reactivate User")).toBeInTheDocument();

      const dialogButtons = screen.getAllByText("Reactivate");
      fireEvent.click(dialogButtons[dialogButtons.length - 1]);

      await waitFor(() => {
        expect(userService.setUserActive).toHaveBeenCalledWith(
          "carol@example.com",
          true,
          false,
        );
        expect(updateLocalUser).toHaveBeenCalledWith(
          "carol@example.com",
          updated,
        );
      });
      expect(mockShowToast).toHaveBeenCalledWith(
        expect.stringContaining("reactivated"),
        "success",
      );
    });

    it("reactivating a scim-managed user with the override switch on calls setUserActive(u, true, true)", async () => {
      mockUseAllUserDetails.mockReturnValue({
        isLoading: false,
        error: null,
        refresh: vi.fn(),
        updateLocalUser: vi.fn(),
        users: [inactiveScimUser],
      });
      vi.mocked(userService.setUserActive).mockResolvedValue({
        ...inactiveScimUser,
        active: true,
      });

      renderPage();

      fireEvent.click(screen.getByRole("button", { name: "Reactivate user" }));

      expect(screen.getByText("Override ownership guard")).toBeInTheDocument();

      const overrideLabel = screen
        .getByText("Override ownership guard")
        .closest("label");
      expect(overrideLabel).not.toBeNull();
      fireEvent.click(within(overrideLabel as HTMLElement).getByRole("switch"));

      const dialogButtons = screen.getAllByText("Reactivate");
      fireEvent.click(dialogButtons[dialogButtons.length - 1]);

      await waitFor(() => {
        expect(userService.setUserActive).toHaveBeenCalledWith(
          "dave@example.com",
          true,
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

      renderPage();

      expect(screen.getByText("carol@example.com")).toBeInTheDocument();

      const showInactiveLabel = screen
        .getByText("Show inactive")
        .closest("label");
      fireEvent.click(
        within(showInactiveLabel as HTMLElement).getByRole("switch"),
      );

      expect(screen.queryByText("carol@example.com")).not.toBeInTheDocument();
    });

    describe("row actions", () => {
      beforeEach(() => {
        mockUseAllUserDetails.mockReturnValue({
          isLoading: false,
          error: null,
          refresh: vi.fn(),
          updateLocalUser: vi.fn(),
          users: [
            { ...adminUser, username: "a b@x.com" },
            { ...inactiveUser, username: "team/1" },
          ],
        });
      });

      it("links each username to its permissions page", () => {
        renderPage();

        expect(screen.getByRole("link", { name: "a b@x.com" })).toHaveAttribute(
          "href",
          "/users/a b@x.com/experiments",
        );
        expect(screen.getByRole("link", { name: "team/1" })).toHaveAttribute(
          "href",
          "/users/team%2F1/experiments",
        );
      });

      it("navigates to the permissions page when the row is clicked", () => {
        renderPage();

        fireEvent.click(within(getRow("a b@x.com")).getByText("Alice"));
        expect(screen.getByTestId("location")).toHaveTextContent(
          "/users/a b@x.com/experiments",
        );
      });

      it("drops the Permissions column and keeps the other columns", () => {
        const { container } = renderPage();

        expect(
          screen.queryByRole("columnheader", { name: "Permissions" }),
        ).not.toBeInTheDocument();
        expect(
          screen.queryByRole("button", { name: /manage permissions/i }),
        ).not.toBeInTheDocument();
        for (const header of [
          "Username",
          "Display name",
          "State",
          "Managed by",
          "Admin",
          "Actions",
        ]) {
          expect(
            screen.getByRole("columnheader", { name: header }),
          ).toBeInTheDocument();
        }
        expect(container.querySelector(".invisible")).toBeNull();
      });

      it("shows Sessions, Deactivate and Reactivate as visible, muted buttons", () => {
        renderPage();

        const activeRow = getRow("a b@x.com");
        const inactiveRow = getRow("team/1");
        const buttons = [
          within(activeRow).getByRole("button", { name: "Sessions" }),
          within(activeRow).getByRole("button", { name: "Deactivate user" }),
          within(inactiveRow).getByRole("button", { name: "Reactivate user" }),
        ];
        for (const button of buttons) {
          expect(button).toBeVisible();
          expect(button).not.toHaveClass("invisible");
          expect(button.closest(".invisible")).toBeNull();
          expect(button).toHaveClass("text-text-primary");
        }
      });

      it("opens the sessions modal without navigating", () => {
        renderPage();

        fireEvent.click(
          within(getRow("a b@x.com")).getByRole("button", { name: "Sessions" }),
        );
        expect(screen.getByTestId("sessions-modal")).toHaveTextContent(
          "a b@x.com",
        );
        expect(screen.getByTestId("location")).toHaveTextContent(/^\/users$/);
      });

      it("opens the deactivate modal without navigating", () => {
        renderPage();
        expect(screen.queryByText("Deactivate User")).not.toBeInTheDocument();

        fireEvent.click(
          within(getRow("a b@x.com")).getByRole("button", {
            name: "Deactivate user",
          }),
        );
        expect(screen.getByText("Deactivate User")).toBeInTheDocument();
        expect(screen.getByTestId("location")).toHaveTextContent(/^\/users$/);
      });

      it("keeps the Show inactive switch working", () => {
        renderPage();

        const showInactiveLabel = screen
          .getByText("Show inactive")
          .closest("label");
        fireEvent.click(
          within(showInactiveLabel as HTMLElement).getByRole("switch"),
        );
        expect(
          screen.queryByRole("link", { name: "team/1" }),
        ).not.toBeInTheDocument();
        expect(screen.getByTestId("location")).toHaveTextContent(/^\/users$/);
      });
    });
  });
});
