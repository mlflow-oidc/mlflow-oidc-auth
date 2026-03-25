import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import WorkspaceDetailPage from "./workspace-detail-page";

import type { WorkspaceUserPermission, WorkspaceGroupPermission, PermissionLevel } from "../../shared/types/entity";
import type { Mock } from "vitest";

const mockNavigate = vi.fn();

vi.mock("react-router", () => ({
  useParams: () => mockParams,
  Navigate: (props: { to: string }) => {
    mockNavigate(props.to);
    return <div data-testid="navigate" data-to={props.to} />;
  },
}));

const mockUseRuntimeConfig: Mock<
  () => { workspaces_enabled: boolean }
> = vi.fn();

vi.mock("../../shared/context/use-runtime-config", () => ({
  useRuntimeConfig: () => mockUseRuntimeConfig(),
}));

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

let mockIsAdmin = true;

vi.mock("../../core/hooks/use-workspace-users", () => ({
  useWorkspaceUsers: () => mockUseWorkspaceUsers(),
}));

vi.mock("../../core/hooks/use-workspace-groups", () => ({
  useWorkspaceGroups: () => mockUseWorkspaceGroups(),
}));

vi.mock("../../core/hooks/use-all-users", () => ({
  useAllUsers: () => ({ allUsers: ["alice", "bob", "newuser"], isLoading: false }),
}));

vi.mock("../../core/hooks/use-all-accounts", () => ({
  useAllServiceAccounts: () => ({ allServiceAccounts: ["svc-build", "svc-deploy"], isLoading: false }),
}));

vi.mock("../../core/hooks/use-all-groups", () => ({
  useAllGroups: () => ({ allGroups: ["admins", "viewers", "newgroup"], isLoading: false }),
}));

vi.mock("../../core/hooks/use-user", () => ({
  useUser: () => ({
    currentUser: {
      is_admin: mockIsAdmin,
      username: "admin",
      display_name: "Admin",
      groups: [],
      id: 1,
      is_service_account: false,
      password_expiration: null,
    },
    isLoading: false,
    error: null,
    refresh: vi.fn(),
  }),
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
  Button: ({ children, onClick, disabled, title }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean; title?: string }) => (
    <button onClick={onClick} disabled={disabled} title={title}>
      {children}
    </button>
  ),
}));

vi.mock("./components/bulk-assign-modal", () => ({
  BulkAssignModal: ({ isOpen, title }: { isOpen: boolean; title: string }) =>
    isOpen ? <div data-testid="bulk-assign-modal">{title}</div> : null,
}));

vi.mock("../permissions/components/grant-permission-modal", () => ({
  GrantPermissionModal: ({
    isOpen,
    title,
    onSave,
    options,
    label,
  }: {
    isOpen: boolean;
    title: string;
    onSave: (name: string, permission: string) => Promise<void>;
    options: string[];
    label: string;
  }) =>
    isOpen ? (
      <div data-testid={`grant-modal-${label}`} title={title}>
        <span data-testid="grant-modal-options">{options.join(",")}</span>
        <button data-testid={`grant-save-${label}`} onClick={() => void onSave(options[0], "READ")}>
          Save
        </button>
      </div>
    ) : null,
}));

describe("WorkspaceDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockParams = { workspaceName: "test-workspace" };
    mockIsAdmin = true;
    mockUseRuntimeConfig.mockReturnValue({ workspaces_enabled: true });
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

  it("renders add user, add service account, and add group buttons", () => {
    render(<WorkspaceDetailPage />);

    expect(screen.getByText("+ Add User")).toBeInTheDocument();
    expect(screen.getByText("+ Add Service Account")).toBeInTheDocument();
    expect(screen.getByText("+ Add Group")).toBeInTheDocument();
  });

  it("opens grant user modal on add user click", () => {
    render(<WorkspaceDetailPage />);

    fireEvent.click(screen.getByText("+ Add User"));

    expect(screen.getByTestId("grant-modal-User")).toBeInTheDocument();
  });

  it("opens grant service account modal on add service account click", () => {
    render(<WorkspaceDetailPage />);

    fireEvent.click(screen.getByText("+ Add Service Account"));

    expect(screen.getByTestId("grant-modal-Service Account")).toBeInTheDocument();
  });

  it("opens grant group modal on add group click", () => {
    render(<WorkspaceDetailPage />);

    fireEvent.click(screen.getByText("+ Add Group"));

    expect(screen.getByTestId("grant-modal-Group")).toBeInTheDocument();
  });

  it("filters available users by excluding already-assigned members", () => {
    mockUseWorkspaceUsers.mockReturnValue({
      workspaceUsers: [{ workspace: "test-workspace", username: "alice", permission: "MANAGE" as PermissionLevel }],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    render(<WorkspaceDetailPage />);

    fireEvent.click(screen.getByText("+ Add User"));

    // alice is already assigned, so only bob and newuser should be available
    const options = screen.getByTestId("grant-modal-options");
    expect(options.textContent).toBe("bob,newuser");
  });

  it("handles user grant permission via GrantPermissionModal", async () => {
    mockRequest.mockResolvedValue({});

    render(<WorkspaceDetailPage />);

    fireEvent.click(screen.getByText("+ Add User"));
    fireEvent.click(screen.getByTestId("grant-save-User"));

    await waitFor(() => {
      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/permissions/workspaces/test-workspace/users",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ username: "alice", permission: "READ" }),
        }),
      );
    });
  });

  it("handles group grant permission via GrantPermissionModal", async () => {
    mockRequest.mockResolvedValue({});

    render(<WorkspaceDetailPage />);

    fireEvent.click(screen.getByText("+ Add Group"));
    fireEvent.click(screen.getByTestId("grant-save-Group"));

    await waitFor(() => {
      expect(mockRequest).toHaveBeenCalledWith(
        "/api/3.0/mlflow/permissions/workspaces/test-workspace/groups",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ group_name: "admins", permission: "READ" }),
        }),
      );
    });
  });

  it("renders Bulk Assign Users button when admin", () => {
    mockIsAdmin = true;
    render(<WorkspaceDetailPage />);
    expect(screen.getByText("Bulk Assign Users")).toBeInTheDocument();
  });

  it("renders Bulk Assign Groups button when admin", () => {
    mockIsAdmin = true;
    render(<WorkspaceDetailPage />);
    expect(screen.getByText("Bulk Assign Groups")).toBeInTheDocument();
  });

  it("does not render bulk assign buttons when not admin", () => {
    mockIsAdmin = false;
    render(<WorkspaceDetailPage />);
    expect(screen.queryByText("Bulk Assign Users")).not.toBeInTheDocument();
    expect(screen.queryByText("Bulk Assign Groups")).not.toBeInTheDocument();
  });

  it("opens bulk assign users modal on click", () => {
    mockIsAdmin = true;
    render(<WorkspaceDetailPage />);

    fireEvent.click(screen.getByText("Bulk Assign Users"));

    expect(screen.getByTestId("bulk-assign-modal")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-assign-modal")).toHaveTextContent("Bulk Assign Users");
  });

  it("opens bulk assign groups modal on click", () => {
    mockIsAdmin = true;
    render(<WorkspaceDetailPage />);

    fireEvent.click(screen.getByText("Bulk Assign Groups"));

    expect(screen.getByTestId("bulk-assign-modal")).toBeInTheDocument();
    expect(screen.getByTestId("bulk-assign-modal")).toHaveTextContent("Bulk Assign Groups");
  });

  it("redirects to home when workspaces are disabled", () => {
    mockUseRuntimeConfig.mockReturnValue({ workspaces_enabled: false });

    render(<WorkspaceDetailPage />);
    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/");
  });
});
