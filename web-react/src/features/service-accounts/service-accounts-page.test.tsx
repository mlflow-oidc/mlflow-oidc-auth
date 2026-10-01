import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ServiceAccountsPage from "./service-accounts-page";
import * as usePagedListModule from "../../core/hooks/use-paged-list";
import { pagedListState } from "../../tests/paged-list-mock";
import * as useCurrentUserModule from "../../core/hooks/use-current-user";
import * as userService from "../../core/services/user-service";
import * as useToastModule from "../../shared/components/toast/use-toast";
import * as useSearchModule from "../../core/hooks/use-search";
import React from "react";

vi.mock("../../core/hooks/use-paged-list");
vi.mock("../../core/hooks/use-current-user");
vi.mock("../../core/services/user-service");
vi.mock("../../shared/components/toast/use-toast");
vi.mock("../../core/hooks/use-search");
vi.mock("../../core/hooks/use-api", () => ({
  useApi: () => ({
    data: [{ username: "sa1", service_account_source: "ci" }],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    isStale: false,
  }),
}));
vi.mock("./hooks/use-service-account-sources", () => ({
  useServiceAccountSources: () => ({
    sources: [
      {
        id: "internal",
        display_name: "Internal (issued access tokens only)",
        type: "internal",
      },
      { id: "ci", display_name: "CI workloads", type: "oidc" },
    ],
    isLoading: false,
  }),
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
  default: ({ isLoading }: { isLoading: boolean }) =>
    isLoading ? <div>Loading...</div> : null,
}));

vi.mock("./components/create-service-account-modal", () => ({
  CreateServiceAccountModal: ({
    isOpen,
    onSave,
  }: {
    isOpen: boolean;
    onSave: (data: {
      name: string;
      display_name: string;
      is_admin: boolean;
      service_account_source: string;
      subject?: string;
    }) => void;
  }) =>
    isOpen ? (
      <div data-testid="create-modal">
        <button
          onClick={() =>
            onSave({
              name: "newsa",
              display_name: "New SA",
              is_admin: false,
              service_account_source: "ci",
              subject: "repo:org/app:ref:refs/heads/main",
            })
          }
        >
          Confirm Create
        </button>
      </div>
    ) : null,
}));

function LocationDisplay() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/service-accounts"]}>
      <Routes>
        <Route
          path="*"
          element={
            <>
              <ServiceAccountsPage />
              <LocationDisplay />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );

describe("ServiceAccountsPage", () => {
  const mockShowToast = vi.fn();
  const mockRefresh = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(usePagedListModule.usePagedList).mockReturnValue(
      pagedListState(["sa1"], { refresh: mockRefresh }),
    );

    vi.spyOn(useCurrentUserModule, "useCurrentUser").mockReturnValue({
      currentUser: { is_admin: true, username: "admin" },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    } as unknown as ReturnType<typeof useCurrentUserModule.useCurrentUser>);

    vi.spyOn(useToastModule, "useToast").mockReturnValue({
      showToast: mockShowToast,
      removeToast: vi.fn(),
    } as unknown as ReturnType<typeof useToastModule.useToast>);

    vi.spyOn(useSearchModule, "useSearch").mockReturnValue({
      searchTerm: "",
      submittedTerm: "",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    } as unknown as ReturnType<typeof useSearchModule.useSearch>);
  });

  it("renders correctly", () => {
    renderPage();
    expect(screen.getByText("sa1")).toBeInTheDocument();
  });

  it("pages service accounts server-side and sends the search term", () => {
    vi.spyOn(useSearchModule, "useSearch").mockReturnValue({
      searchTerm: "sa",
      submittedTerm: "sa",
      handleInputChange: vi.fn(),
      handleSearchSubmit: vi.fn(),
      handleClearSearch: vi.fn(),
    } as unknown as ReturnType<typeof useSearchModule.useSearch>);

    renderPage();
    expect(usePagedListModule.usePagedList).toHaveBeenCalledWith(
      userService.fetchServiceAccountsPage,
      "sa",
    );
  });

  it("opens create modal", () => {
    renderPage();
    fireEvent.click(screen.getByText("Create Service Account"));
    expect(screen.getByTestId("create-modal")).toBeInTheDocument();
  });

  it("creates service account", async () => {
    const mockCreateUser = vi.spyOn(userService, "createUser");
    mockCreateUser.mockResolvedValue({} as unknown as { message: string });
    renderPage();

    fireEvent.click(screen.getByText("Create Service Account"));
    fireEvent.click(screen.getByText("Confirm Create"));

    await waitFor(() => {
      expect(mockCreateUser).toHaveBeenCalledWith({
        username: "newsa",
        display_name: "New SA",
        is_admin: false,
        is_service_account: true,
        service_account_source: "ci",
        subject: "repo:org/app:ref:refs/heads/main",
      });
      expect(mockShowToast).toHaveBeenCalledWith(
        "Service account newsa created successfully",
        "success",
      );
    });
  });

  it("shows how each service account signs in, and opens the change dialog", () => {
    renderPage();

    expect(screen.getByText("Signs in with")).toBeInTheDocument();
    expect(screen.getByText("CI workloads")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("How it signs in"));
    expect(screen.getByText("How sa1 signs in")).toBeInTheDocument();
  });

  it("handles creation error", async () => {
    const mockCreateUser = vi.spyOn(userService, "createUser");
    mockCreateUser.mockRejectedValue(new Error("Creation failed"));
    renderPage();

    fireEvent.click(screen.getByText("Create Service Account"));
    fireEvent.click(screen.getByText("Confirm Create"));

    await waitFor(() => {
      expect(mockShowToast).toHaveBeenCalledWith(
        "Failed to create service account",
        "error",
      );
    });
  });

  it("deletes service account", async () => {
    const mockDeleteUser = vi.spyOn(userService, "deleteUser");
    mockDeleteUser.mockResolvedValue(undefined);
    renderPage();

    const deleteButton = screen.getByTitle("Remove service account");
    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(mockDeleteUser).toHaveBeenCalledWith("sa1");
      expect(mockShowToast).toHaveBeenCalledWith(
        "Service account sa1 removed successfully",
        "success",
      );
      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  it("does not navigate when the remove action is clicked", async () => {
    vi.spyOn(userService, "deleteUser").mockResolvedValue(undefined);
    renderPage();

    fireEvent.click(
      screen.getByRole("button", { name: "Remove service account" }),
    );
    await waitFor(() => expect(userService.deleteUser).toHaveBeenCalled());
    expect(screen.getByTestId("location")).toHaveTextContent(
      /^\/service-accounts$/,
    );
  });

  describe("row navigation", () => {
    beforeEach(() => {
      vi.mocked(usePagedListModule.usePagedList).mockReturnValue(
        pagedListState(["a b@x.com", "team/1"], { refresh: mockRefresh }),
      );
    });

    it("links each name to its permissions page", () => {
      renderPage();

      expect(screen.getByRole("link", { name: "a b@x.com" })).toHaveAttribute(
        "href",
        "/service-accounts/a b@x.com/experiments",
      );
      expect(screen.getByRole("link", { name: "team/1" })).toHaveAttribute(
        "href",
        "/service-accounts/team%2F1/experiments",
      );
    });

    it("navigates when the row is clicked", () => {
      renderPage();

      const row = screen
        .getByRole("link", { name: "team/1" })
        .closest<HTMLElement>('[role="row"]');
      expect(row).not.toBeNull();
      fireEvent.click(within(row as HTMLElement).getAllByRole("cell")[1]);
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/service-accounts/team%2F1/experiments",
      );
    });

    it("has no Permissions column or hidden elements and a muted remove action", () => {
      const { container } = renderPage();

      expect(
        screen.queryByRole("columnheader", { name: "Permissions" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: /manage permissions/i }),
      ).not.toBeInTheDocument();
      expect(container.querySelector(".invisible")).toBeNull();
      const removeButtons = screen.getAllByRole("button", {
        name: "Remove service account",
      });
      expect(removeButtons).toHaveLength(2);
      removeButtons.forEach((button) =>
        expect(button).toHaveClass("text-text-primary"),
      );
    });

    it("keeps the name link keyboard focusable", () => {
      renderPage();
      const link = screen.getByRole("link", { name: "a b@x.com" });
      link.focus();
      expect(document.activeElement).toBe(link);
    });
  });
});
