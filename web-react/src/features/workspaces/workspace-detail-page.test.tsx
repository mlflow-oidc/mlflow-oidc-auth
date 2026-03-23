import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import WorkspaceDetailPage from "./workspace-detail-page";

import type { WorkspaceUserPermission, WorkspaceGroupPermission, PermissionLevel } from "../../shared/types/entity";
import type { Mock } from "vitest";

const mockShowToast = vi.fn();

const mockUseWorkspaceUsers: Mock<
  () => {
    workspaceUsers: WorkspaceUserPermission[];
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
  }
> = vi.fn();

const mockUseWorkspaceGroups: Mock<
  () => {
    workspaceGroups: WorkspaceGroupPermission[];
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
  }
> = vi.fn();

const mockRequest = vi.fn();

let mockParams: Record<string, string> = { workspaceName: "test-workspace" };

vi.mock("react-router", () => ({
  useParams: () => mockParams,
}));

vi.mock("../../core/hooks/use-workspace-users", () => ({
  useWorkspaceUsers: () => mockUseWorkspaceUsers(),
}));

vi.mock("../../core/hooks/use-workspace-groups", () => ({
  useWorkspaceGroups: () => mockUseWorkspaceGroups(),
}));

vi.mock("../../shared/components/toast/use-toast", () => ({
  useToast: () => ({ showToast: mockShowToast }),
}));

vi.mock("../../core/services/api-utils", () => ({
  request: (...args: unknown[]) => mockRequest(...args),
}));

vi.mock("../../core/configs/api-endpoints", () => ({
  DYNAMIC_API_ENDPOINTS: {
    WORKSPACE_USERS: (workspace: string) => `/api/3.0/mlflow/permissions/workspaces/${workspace}/users`,
    WORKSPACE_GROUPS: (workspace: string) => `/api/3.0/mlflow/permissions/workspaces/${workspace}/groups`,
    WORKSPACE_USER: (workspace: string, username: string) => `/api/3.0/mlflow/permissions/workspaces/${workspace}/users/${username}`,
    WORKSPACE_GROUP: (workspace: string, groupName: string) => `/api/3.0/mlflow/permissions/workspaces/${workspace}/groups/${groupName}`,
  },
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

vi.mock("../../shared/components/modal", () => ({
  Modal: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="modal" title={title}>
      {children}
    </div>
  ),
}));

vi.mock("../../shared/components/permission-level-select", () => ({
  PermissionLevelSelect: () => <div data-testid="permission-level-select" />,
}));

vi.mock("../../shared/components/icon-button", () => ({
  IconButton: ({ title, onClick }: { title: string; onClick: () => void }) => (
    <button data-testid={`icon-button-${title}`} onClick={onClick}>
      {title}
    </button>
  ),
}));

vi.mock("../../shared/components/button", () => ({
  Button: ({ children, onClick, disabled }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean }) => (
    <button onClick={onClick} disabled={disabled}>
      {children}
    </button>
  ),
}));

describe("WorkspaceDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockParams = { workspaceName: "test-workspace" };
    mockRequest.mockResolvedValue({});
    mockUseWorkspaceUsers.mockReturnValue({
      workspaceUsers: [],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    mockUseWorkspaceGroups.mockReturnValue({
      workspaceGroups: [],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
  });

  it("renders workspace name required when no param", () => {
    mockParams = {};

    render(<WorkspaceDetailPage />);
    expect(screen.getByText("Workspace name is required.")).toBeInTheDocument();
  });

  it("renders users and groups sections", () => {
    render(<WorkspaceDetailPage />);

    expect(screen.getByText("Users (0)")).toBeInTheDocument();
    expect(screen.getByText("Groups (0)")).toBeInTheDocument();
  });

  it("renders workspace name in title", () => {
    render(<WorkspaceDetailPage />);

    expect(screen.getByTestId("page-container")).toHaveAttribute("title", "Permissions for Workspace test-workspace");
  });

  it("renders user members with permissions", () => {
    mockUseWorkspaceUsers.mockReturnValue({
      workspaceUsers: [
        { workspace: "test-workspace", username: "alice", permission: "MANAGE" as PermissionLevel },
        { workspace: "test-workspace", username: "bob", permission: "READ" as PermissionLevel },
      ],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<WorkspaceDetailPage />);

    expect(screen.getByText("alice")).toBeInTheDocument();
    expect(screen.getByText("MANAGE")).toBeInTheDocument();
    expect(screen.getByText("bob")).toBeInTheDocument();
    expect(screen.getByText("READ")).toBeInTheDocument();
    expect(screen.getByText("Users (2)")).toBeInTheDocument();
  });

  it("renders group members with permissions", () => {
    mockUseWorkspaceGroups.mockReturnValue({
      workspaceGroups: [
        { workspace: "test-workspace", group_name: "admins", permission: "MANAGE" as PermissionLevel },
        { workspace: "test-workspace", group_name: "viewers", permission: "READ" as PermissionLevel },
      ],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<WorkspaceDetailPage />);

    expect(screen.getByText("admins")).toBeInTheDocument();
    expect(screen.getByText("viewers")).toBeInTheDocument();
    expect(screen.getByText("Groups (2)")).toBeInTheDocument();
  });

  it("renders loading state", () => {
    mockUseWorkspaceUsers.mockReturnValue({
      workspaceUsers: [],
      isLoading: true,
      error: null,
      refresh: vi.fn(),
    });

    render(<WorkspaceDetailPage />);

    expect(screen.getAllByText("Loading...").length).toBeGreaterThanOrEqual(1);
  });

  it("renders empty state when no members", () => {
    render(<WorkspaceDetailPage />);

    expect(screen.getByText("No users assigned.")).toBeInTheDocument();
    expect(screen.getByText("No groups assigned.")).toBeInTheDocument();
  });

  it("handles user grant permission", async () => {
    mockRequest.mockResolvedValue({});

    render(<WorkspaceDetailPage />);

    // Click the add button for users
    const addButtons = screen.getAllByText("+ Add Users");
    fireEvent.click(addButtons[0]);

    // Fill in the name
    const nameInput = screen.getByPlaceholderText("Enter username");
    fireEvent.change(nameInput, { target: { value: "newuser" } });

    // Click save
    const saveButtons = screen.getAllByText("Save");
    fireEvent.click(saveButtons[0]);

    await waitFor(() => {
      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/permissions/workspaces/test-workspace/users",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ username: "newuser", permission: "READ" }),
        }),
      );
    });
  });

  it("handles group grant permission", async () => {
    mockRequest.mockResolvedValue({});

    render(<WorkspaceDetailPage />);

    // Click the add button for groups
    const addButtons = screen.getAllByText("+ Add Groups");
    fireEvent.click(addButtons[0]);

    // Fill in the name
    const nameInput = screen.getByPlaceholderText("Enter group name");
    fireEvent.change(nameInput, { target: { value: "newgroup" } });

    // Click save
    const saveButtons = screen.getAllByText("Save");
    fireEvent.click(saveButtons[0]);

    await waitFor(() => {
      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/permissions/workspaces/test-workspace/groups",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ group_name: "newgroup", permission: "READ" }),
        }),
      );
    });
  });
});
