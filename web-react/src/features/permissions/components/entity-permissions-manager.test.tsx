import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { EntityPermissionsManager } from "./entity-permissions-manager";
import * as usePermissionsManagementModule from "../hooks/use-permissions-management";
import * as useAllUsersModule from "../../../core/hooks/use-all-users";
import * as useAllAccountsModule from "../../../core/hooks/use-all-accounts";
import * as useAllGroupsModule from "../../../core/hooks/use-all-groups";
import * as useSearchModule from "../../../core/hooks/use-search";
import type { EntityPermission } from "../../../shared/types/entity";

vi.mock("../hooks/use-permissions-management");
vi.mock("../../../core/hooks/use-all-users");
vi.mock("../../../core/hooks/use-all-accounts");
vi.mock("../../../core/hooks/use-all-groups");
vi.mock("../../../core/hooks/use-search");

describe("EntityPermissionsManager", () => {
    const mockRefresh = vi.fn();
    const mockHandleEditClick = vi.fn();
    const mockHandleSavePermission = vi.fn();
    const mockHandleRemovePermission = vi.fn();
    const mockHandleModalClose = vi.fn();
    const mockHandleGrantPermission = vi.fn().mockResolvedValue(true);

    const mockPermissions: EntityPermission[] = [
        { name: "user1", permission: "READ", kind: "user" },
        { name: "group1", permission: "EDIT", kind: "group" },
    ];

    const defaultManagement = {
        isModalOpen: false,
        editingItem: null,
        isSaving: false,
        handleEditClick: mockHandleEditClick,
        handleSavePermission: mockHandleSavePermission,
        handleRemovePermission: mockHandleRemovePermission,
        handleModalClose: mockHandleModalClose,
        handleGrantPermission: mockHandleGrantPermission,
    };

    const defaultSearch = {
        searchTerm: "",
        submittedTerm: "",
        handleInputChange: vi.fn(),
        handleSearchSubmit: vi.fn(),
        handleClearSearch: vi.fn(),
    };

    beforeEach(() => {
        vi.clearAllMocks();
        vi.spyOn(usePermissionsManagementModule, "usePermissionsManagement").mockReturnValue(defaultManagement as any);
        vi.spyOn(useAllUsersModule, "useAllUsers").mockReturnValue({ allUsers: ["user1", "user2"] } as any);
        vi.spyOn(useAllAccountsModule, "useAllServiceAccounts").mockReturnValue({ allServiceAccounts: ["sa1"] } as any);
        vi.spyOn(useAllGroupsModule, "useAllGroups").mockReturnValue({ allGroups: ["group1", "group2"] } as any);
        vi.spyOn(useSearchModule, "useSearch").mockReturnValue(defaultSearch as any);
    });

    const renderManager = (props = {}) => {
        return render(
            <EntityPermissionsManager
                resourceId="res-1"
                resourceName="Resource 1"
                resourceType="experiments"
                permissions={mockPermissions}
                isLoading={false}
                error={null}
                refresh={mockRefresh}
                {...props}
            />
        );
    };

    it("renders permission table items", () => {
        renderManager();
        expect(screen.getByText("user1")).toBeDefined();
        expect(screen.getByText("group1")).toBeDefined();
        expect(screen.getByText("READ")).toBeDefined();
        expect(screen.getByText("EDIT")).toBeDefined();
    });

    it("renders loading and error states", () => {
        renderManager({ isLoading: true });
        expect(screen.getByText(/Loading permissions/i)).toBeDefined();

        renderManager({ isLoading: false, error: new Error("Failed") });
        expect(screen.getByText(/Failed/i)).toBeDefined();
    });

    it("handles search", () => {
        renderManager();
        const searchInput = screen.getByPlaceholderText(/Search permissions/i);
        fireEvent.change(searchInput, { target: { value: "test" } });
        fireEvent.submit(searchInput.closest("form")!);
        expect(defaultSearch.handleSearchSubmit).toHaveBeenCalled();
    });

    it("opens edit modal", () => {
        vi.spyOn(usePermissionsManagementModule, "usePermissionsManagement").mockReturnValue({
            ...defaultManagement,
            isModalOpen: true,
            editingItem: mockPermissions[0],
        } as any);
        
        renderManager();
        // The title matches "Edit Experiment res-1 permissions for user1"
        expect(screen.getByText(/Edit Experiment/i)).toBeDefined();
        expect(screen.getByText(/permissions for user1/i)).toBeDefined();
    });

    it("opens grant user modal", async () => {
        renderManager();
        const addButton = screen.getByRole("button", { name: /^\+ Add$/ }); // First "+ Add" button is for users
        fireEvent.click(addButton);
        
        expect(screen.getByText(/Grant user permissions/i)).toBeDefined();
        
        const select = screen.getByLabelText(/User/i);
        fireEvent.change(select, { target: { value: "user2" } });
        
        const saveButton = screen.getByRole("button", { name: "Save" });
        fireEvent.click(saveButton);
        
        await waitFor(() => {
            expect(mockHandleGrantPermission).toHaveBeenCalledWith("user2", "READ");
        });
    });

    it("opens grant service account modal", async () => {
        renderManager();
        const addButton = screen.getByRole("button", { name: /\+ Add Service Account/i });
        fireEvent.click(addButton);
        
        expect(screen.getByText(/Grant service account permissions/i)).toBeDefined();
        
        const select = screen.getByLabelText(/Service account/i);
        fireEvent.change(select, { target: { value: "sa1" } });
        
        const saveButton = screen.getByRole("button", { name: "Save" });
        fireEvent.click(saveButton);
        
        await waitFor(() => {
            expect(mockHandleGrantPermission).toHaveBeenCalledWith("sa1", "READ");
        });
    });

    it("opens grant group modal", async () => {
        renderManager();
        const addButton = screen.getByRole("button", { name: /\+ Add Group/i });
        fireEvent.click(addButton);
        
        expect(screen.getByText(/Grant group permissions/i)).toBeDefined();
        
        const select = screen.getByLabelText(/Group/i);
        fireEvent.change(select, { target: { value: "group2" } });
        
        const saveButton = screen.getByRole("button", { name: "Save" });
        fireEvent.click(saveButton);
        
        await waitFor(() => {
            expect(mockHandleGrantPermission).toHaveBeenCalledWith("group2", "READ", "group");
        });
    });

    it("handles remove permission", async () => {
        renderManager();
        const removeButtons = screen.getAllByTitle("Remove permission");
        fireEvent.click(removeButtons[0]);
        
        expect(mockHandleRemovePermission).toHaveBeenCalledWith(mockPermissions[0]);
    });

    it("filters available users/groups correctly", () => {
        // user1 and group1 are already in mockPermissions
        renderManager();
        
        // Open user grant modal
        fireEvent.click(screen.getByRole("button", { name: /^\+ Add$/ }));
        const userOptions = screen.getAllByRole("option");
        // Options should be: "Select user...", "user2"
        expect(userOptions.map(o => (o as HTMLOptionElement).value)).toContain("user2");
        expect(userOptions.map(o => (o as HTMLOptionElement).value)).not.toContain("user1");
        
        // Close modal (mocking doesn't really close it here, but we can just check groups)
        fireEvent.click(screen.getByText("Cancel"));
        
        // Open group grant modal
        fireEvent.click(screen.getByRole("button", { name: /\+ Add Group/i }));
        const groupOptions = screen.getAllByRole("option");
        expect(groupOptions.map(o => (o as HTMLOptionElement).value)).toContain("group2");
        expect(groupOptions.map(o => (o as HTMLOptionElement).value)).not.toContain("group1");
    });
});
