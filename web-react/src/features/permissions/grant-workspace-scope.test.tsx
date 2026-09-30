import { describe, it, expect, vi, beforeEach } from "vitest";
import type React from "react";
import { render, screen, renderHook } from "@testing-library/react";
import { RuntimeConfigContext } from "../../shared/context/use-runtime-config";
import { WorkspaceContext } from "../../shared/context/use-workspace";
import type { RuntimeConfig } from "../../shared/services/runtime-config";
import type { PermissionType } from "../../shared/types/entity";
import { useGrantWorkspaceScope } from "./hooks/use-grant-workspace-scope";
import { EntityPermissionsManager } from "./components/entity-permissions-manager";
import { AddRegexRuleModal } from "./components/add-regex-rule-modal";
import * as usePermissionsManagementModule from "./hooks/use-permissions-management";
import * as useAllUsersModule from "../../core/hooks/use-all-users";
import * as useAllAccountsModule from "../../core/hooks/use-all-accounts";
import * as useAllGroupsModule from "../../core/hooks/use-all-groups";

vi.mock("./hooks/use-permissions-management");
vi.mock("../../core/hooks/use-all-users");
vi.mock("../../core/hooks/use-all-accounts");
vi.mock("../../core/hooks/use-all-groups");

const CONFIG: RuntimeConfig = {
  basePath: "",
  uiPath: "/oidc/ui",
  provider: "oidc",
  authenticated: true,
  gen_ai_gateway_enabled: true,
  workspaces_enabled: true,
};

function wrapper(workspacesEnabled: boolean, selected: string | null) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <RuntimeConfigContext
        value={{ ...CONFIG, workspaces_enabled: workspacesEnabled }}
      >
        <WorkspaceContext
          value={{ selectedWorkspace: selected, setSelectedWorkspace: vi.fn() }}
        >
          {children}
        </WorkspaceContext>
      </RuntimeConfigContext>
    );
  };
}

describe("useGrantWorkspaceScope", () => {
  it.each<PermissionType>([
    "models",
    "prompts",
    "ai-endpoints",
    "ai-secrets",
    "ai-models",
  ])("%s grants belong to the selected workspace", (type) => {
    const { result } = renderHook(() => useGrantWorkspaceScope(type), {
      wrapper: wrapper(true, "team-a"),
    });
    expect(result.current).toEqual({
      scoped: true,
      workspace: "team-a",
      canChange: true,
    });
  });

  it("blocks changes to workspace-scoped grants while All Workspaces is selected", () => {
    const { result } = renderHook(() => useGrantWorkspaceScope("models"), {
      wrapper: wrapper(true, null),
    });
    expect(result.current.canChange).toBe(false);
  });

  it("does not scope experiment grants, which are keyed by id", () => {
    const { result } = renderHook(() => useGrantWorkspaceScope("experiments"), {
      wrapper: wrapper(true, null),
    });
    expect(result.current).toEqual({
      scoped: false,
      workspace: null,
      canChange: true,
    });
  });

  it("does not scope anything with workspaces disabled, or outside a runtime config", () => {
    expect(
      renderHook(() => useGrantWorkspaceScope("models"), {
        wrapper: wrapper(false, null),
      }).result.current.canChange,
    ).toBe(true);
    expect(
      renderHook(() => useGrantWorkspaceScope("models")).result.current.scoped,
    ).toBe(false);
  });
});

describe("EntityPermissionsManager workspace scope", () => {
  beforeEach(() => {
    vi.spyOn(
      usePermissionsManagementModule,
      "usePermissionsManagement",
    ).mockReturnValue({
      isModalOpen: false,
      editingItem: null,
      isSaving: false,
      handleEditClick: vi.fn(),
      handleSavePermission: vi.fn(),
      handleRemovePermission: vi.fn(),
      handleModalClose: vi.fn(),
      handleGrantPermission: vi.fn(),
    });
    vi.spyOn(useAllUsersModule, "useAllUsers").mockReturnValue({
      allUsers: ["u1", "u2"],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    vi.spyOn(useAllAccountsModule, "useAllServiceAccounts").mockReturnValue({
      allServiceAccounts: ["sa1"],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
    vi.spyOn(useAllGroupsModule, "useAllGroups").mockReturnValue({
      allGroups: ["g1"],
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
  });

  const renderFor = (
    type: PermissionType,
    selected: string | null,
    enabled = true,
  ) =>
    render(
      <EntityPermissionsManager
        resourceId="churn"
        resourceName="churn"
        resourceType={type}
        permissions={[{ name: "u1", permission: "READ", kind: "user" }]}
        isLoading={false}
        error={null}
        refresh={vi.fn()}
      />,
      { wrapper: wrapper(enabled, selected) },
    );

  it("names the workspace the grants belong to and allows changes", () => {
    renderFor("models", "team-a");

    expect(screen.getByRole("status")).toHaveTextContent(
      "Grants shown here belong to workspace team-a",
    );
    expect(screen.getByRole("button", { name: "+ Add" })).toBeEnabled();
    expect(screen.getByTitle("Edit permission")).toBeEnabled();
  });

  it("with All Workspaces, says these are default's grants and blocks every change", () => {
    renderFor("ai-endpoints", null);

    expect(screen.getByRole("status")).toHaveTextContent(
      "These are the default workspace's grants",
    );
    for (const name of ["+ Add", "+ Add Service Account", "+ Add Group"]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
    for (const control of screen.getAllByTitle(
      "Choose a workspace in the header to change grants",
    )) {
      expect(control).toBeDisabled();
    }
  });

  it("leaves experiment grants and workspace-disabled deployments unchanged", () => {
    const { unmount } = renderFor("experiments", null);
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByRole("button", { name: "+ Add" })).toBeEnabled();
    unmount();

    renderFor("models", null, false);
    expect(screen.queryByRole("status")).toBeNull();
    expect(screen.getByRole("button", { name: "+ Add" })).toBeEnabled();
  });
});

describe("AddRegexRuleModal workspace note", () => {
  it("says a pattern matches every workspace when workspaces are enabled", () => {
    render(
      <AddRegexRuleModal
        isOpen={true}
        type="models"
        onClose={vi.fn()}
        onSave={vi.fn()}
        isLoading={false}
      />,
      { wrapper: wrapper(true, "team-a") },
    );
    expect(
      screen.getByText(/matches resource names in every workspace/),
    ).toBeInTheDocument();
  });

  it("says nothing with workspaces disabled", () => {
    render(
      <AddRegexRuleModal
        isOpen={true}
        type="models"
        onClose={vi.fn()}
        onSave={vi.fn()}
        isLoading={false}
      />,
      { wrapper: wrapper(false, null) },
    );
    expect(screen.queryByText(/every workspace/)).toBeNull();
  });
});
