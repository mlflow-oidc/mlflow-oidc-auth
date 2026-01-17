import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { EntityPermissionsManager } from "./entity-permissions-manager";

const mockUsePermissionsManagement = vi.fn();
const mockUseAllUsers = vi.fn();
const mockUseAllServiceAccounts = vi.fn();
const mockUseAllGroups = vi.fn();
const mockUseSearch = vi.fn();

vi.mock("../hooks/use-permissions-management", () => ({
  usePermissionsManagement: () => mockUsePermissionsManagement(),
}));

vi.mock("../../../core/hooks/use-all-users", () => ({
  useAllUsers: () => mockUseAllUsers(),
}));

vi.mock("../../../core/hooks/use-all-accounts", () => ({
  useAllServiceAccounts: () => mockUseAllServiceAccounts(),
}));

vi.mock("../../../core/hooks/use-all-groups", () => ({
  useAllGroups: () => mockUseAllGroups(),
}));

vi.mock("../../../core/hooks/use-search", () => ({
  useSearch: () => mockUseSearch(),
}));

vi.mock("../../../shared/components/page/page-status", () => ({
  default: ({ isLoading, error }: any) => {
    if (isLoading) return <div>Loading permissions list...</div>;
    if (error) return <div>Error</div>;
    return null;
  },
}));

vi.mock("../../../shared/components/entity-list-table", () => ({
  EntityListTable: ({ data }: any) => (
    <div data-testid="entity-list">
      {data.map((item: any) => (
        <div key={item.name}>{item.name} - {item.permission}</div>
      ))}
    </div>
  ),
}));

vi.mock("../../../shared/components/button", () => ({
  Button: ({ children, onClick, disabled }: any) => (
      <button onClick={onClick} disabled={disabled}>{children}</button>
  ),
}));

vi.mock("./grant-permission-modal", () => ({
  GrantPermissionModal: ({ isOpen, onSave }: any) => isOpen ? (
    <div data-testid="grant-modal">
      <button onClick={() => onSave("newuser", "READ")}>Confirm Grant</button>
    </div>
  ) : null,
}));

describe("EntityPermissionsManager", () => {
  beforeEach(() => {
    mockUsePermissionsManagement.mockReturnValue({
        isModalOpen: false,
        editingItem: null,
        isSaving: false,
        handleEditClick: vi.fn(),
        handleSavePermission: vi.fn(),
        handleRemovePermission: vi.fn(),
        handleModalClose: vi.fn(),
        handleGrantPermission: vi.fn(),
    });
    mockUseAllUsers.mockReturnValue({ allUsers: ["user1"] });
    mockUseAllServiceAccounts.mockReturnValue({ allServiceAccounts: ["sa1"] });
    mockUseAllGroups.mockReturnValue({ allGroups: ["group1"] });
    mockUseSearch.mockReturnValue({
        searchTerm: "",
        submittedTerm: "",
        handleInputChange: vi.fn(),
        handleSearchSubmit: vi.fn(),
        handleClearSearch: vi.fn(),
    });
  });

  it("renders permissions list", () => {
    render(
        <EntityPermissionsManager 
            resourceId="1" 
            resourceName="res1" 
            resourceType="experiments"
            permissions={[{ name: "user1", permission: "READ", kind: "user" }]}
            isLoading={false}
            error={null}
            refresh={vi.fn()}
        />
    );
    expect(screen.getByText("user1 - READ")).toBeInTheDocument();
  });

  it("opens grant modal", () => {
    render(
        <EntityPermissionsManager 
            resourceId="1" 
            resourceName="res1" 
            resourceType="experiments"
            permissions={[]}
            isLoading={false}
            error={null}
            refresh={vi.fn()}
        />
    );
    
    expect(screen.queryByTestId("grant-modal")).not.toBeInTheDocument();
    
    // Available users has "user1"
    fireEvent.click(screen.getByText("+ Add"));
    
    expect(screen.getByTestId("grant-modal")).toBeInTheDocument();
  });
});
