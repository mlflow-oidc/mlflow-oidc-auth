import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { EntityPermissionsPageLayout } from "./entity-permissions-page-layout";
import type { EntityPermission, PermissionType } from "../../../shared/types/entity";
import type { Mock } from "vitest";

interface EntityPermissionsManagerProps {
  resourceId: string;
  resourceName: string;
  resourceType: PermissionType;
  permissions: EntityPermission[];
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
}

const mockEntityPermissionsManager: Mock<(props: EntityPermissionsManagerProps) => void> = vi.fn();

vi.mock("./entity-permissions-manager", () => ({
  EntityPermissionsManager: (props: EntityPermissionsManagerProps) => {
    mockEntityPermissionsManager(props);
    return <div data-testid="permissions-manager" />;
  },
}));

vi.mock("../../../shared/components/page/page-container", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="page-container" title={title}>
      {children}
    </div>
  ),
}));

describe("EntityPermissionsPageLayout", () => {
  const defaultProps = {
    title: "Test Title",
    resourceId: "res-123",
    resourceName: "Resource Name",
    resourceType: "experiments" as PermissionType,
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  };

  it("renders correctly with basic props", () => {
    render(<EntityPermissionsPageLayout {...defaultProps} />);

    expect(screen.getByTestId("page-container")).toHaveAttribute("title", "Test Title");
    expect(screen.getByTestId("permissions-manager")).toBeInTheDocument();

    const lastCall = mockEntityPermissionsManager.mock.calls[0][0];
    expect(lastCall.resourceId).toBe("res-123");
    expect(lastCall.resourceName).toBe("Resource Name");
    expect(lastCall.resourceType).toBe("experiments");
  });

  it("combines user and group permissions correctly", () => {
    const userPermissions: EntityPermission[] = [
      { name: "user1", kind: "user", permission: "READ" },
    ];
    const groupPermissions: EntityPermission[] = [
      { name: "group1", kind: "group", permission: "EDIT" },
    ];

    render(
      <EntityPermissionsPageLayout
        {...defaultProps}
        userPermissions={userPermissions}
        groupPermissions={groupPermissions}
      />
    );

    const lastCall = mockEntityPermissionsManager.mock.calls[mockEntityPermissionsManager.mock.calls.length - 1][0];
    expect(lastCall.permissions).toHaveLength(2);
    expect(lastCall.permissions).toEqual(
      expect.arrayContaining([
        { name: "user1", kind: "user", permission: "READ" },
        { name: "group1", kind: "group", permission: "EDIT" },
      ])
    );
  });

  it("passes loading and error states to manager", () => {
    const error = new Error("Test error");
    render(<EntityPermissionsPageLayout {...defaultProps} isLoading={true} error={error} />);

    const lastCall = mockEntityPermissionsManager.mock.calls[mockEntityPermissionsManager.mock.calls.length - 1][0];
    expect(lastCall.isLoading).toBe(true);
    expect(lastCall.error).toBe(error);
  });

  it("passes refresh callback to manager", () => {
    const refresh = vi.fn();
    render(<EntityPermissionsPageLayout {...defaultProps} refresh={refresh} />);

    const lastCall = mockEntityPermissionsManager.mock.calls[mockEntityPermissionsManager.mock.calls.length - 1][0];
    lastCall.refresh();
    expect(refresh).toHaveBeenCalled();
  });
});
