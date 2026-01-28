import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ServiceAccountsPage from "./service-accounts-page";
import * as useAllAccountsModule from "../../core/hooks/use-all-accounts";
import * as useCurrentUserModule from "../../core/hooks/use-current-user";
import * as userService from "../../core/services/user-service";
import * as useToastModule from "../../shared/components/toast/use-toast";
import * as useSearchModule from "../../core/hooks/use-search";
import React from "react";

vi.mock("../../core/hooks/use-all-accounts");
vi.mock("../../core/hooks/use-current-user");
vi.mock("../../core/services/user-service");
vi.mock("../../shared/components/toast/use-toast");
vi.mock("../../core/hooks/use-search");

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

vi.mock("../../shared/components/entity-list-table", () => ({
  EntityListTable: ({
    data,
    columns,
  }: {
    data: { username: string }[];
    columns: {
      header: string;
      render: (user: { username: string }) => React.ReactNode;
    }[];
  }) => (
    <div data-testid="sa-list">
      {data.map((item) => (
        <div key={item.username}>
          {item.username}
          {columns.find((c) => c.header === "Actions")?.render(item)}
        </div>
      ))}
    </div>
  ),
}));

vi.mock("../../shared/components/icon-button", () => ({
  IconButton: ({ title, onClick }: { title: string; onClick: () => void }) => (
    <button onClick={onClick} title={title}>
      {title}
    </button>
  ),
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
    }) => void;
  }) =>
    isOpen ? (
      <div data-testid="create-modal">
        <button
          onClick={() =>
            onSave({ name: "newsa", display_name: "New SA", is_admin: false })
          }
        >
          Confirm Create
        </button>
      </div>
    ) : null,
}));

describe("ServiceAccountsPage", () => {
  const mockShowToast = vi.fn();
  const mockRefresh = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.spyOn(useAllAccountsModule, "useAllServiceAccounts").mockReturnValue({
      allServiceAccounts: ["sa1"],
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    } as unknown as ReturnType<
      typeof useAllAccountsModule.useAllServiceAccounts
    >);

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
    render(<ServiceAccountsPage />);
    expect(screen.getByText("sa1")).toBeInTheDocument();
  });

  it("opens create modal", () => {
    render(<ServiceAccountsPage />);
    fireEvent.click(screen.getByText("Create Service Account"));
    expect(screen.getByTestId("create-modal")).toBeInTheDocument();
  });

  it("creates service account", async () => {
    const mockCreateUser = vi.spyOn(userService, "createUser");
    mockCreateUser.mockResolvedValue({} as unknown as { message: string });
    render(<ServiceAccountsPage />);

    fireEvent.click(screen.getByText("Create Service Account"));
    fireEvent.click(screen.getByText("Confirm Create"));

    await waitFor(() => {
      expect(mockCreateUser).toHaveBeenCalledWith({
        username: "newsa",
        display_name: "New SA",
        is_admin: false,
        is_service_account: true,
      });
      expect(mockShowToast).toHaveBeenCalledWith(
        "Service account newsa created successfully",
        "success",
      );
    });
  });

  it("handles creation error", async () => {
    const mockCreateUser = vi.spyOn(userService, "createUser");
    mockCreateUser.mockRejectedValue(new Error("Creation failed"));
    render(<ServiceAccountsPage />);

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
    render(<ServiceAccountsPage />);

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
});
