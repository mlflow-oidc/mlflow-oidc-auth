import { useState } from "react";
import { useParams } from "react-router";
import { useWorkspaceUsers } from "../../core/hooks/use-workspace-users";
import { useWorkspaceGroups } from "../../core/hooks/use-workspace-groups";
import { useAllUsers } from "../../core/hooks/use-all-users";
import { useAllServiceAccounts } from "../../core/hooks/use-all-accounts";
import { useAllGroups } from "../../core/hooks/use-all-groups";
import { useUser } from "../../core/hooks/use-user";
import { request } from "../../core/services/api-utils";
import { DYNAMIC_API_ENDPOINTS } from "../../core/configs/api-endpoints";
import { useToast } from "../../shared/components/toast/use-toast";
import { Button } from "../../shared/components/button";
import PageContainer from "../../shared/components/page/page-container";
import { GrantPermissionModal } from "../permissions/components/grant-permission-modal";
import type { PermissionLevel } from "../../shared/types/entity";
import WorkspaceMembersSection from "./components/workspace-members-section";
import { BulkAssignModal } from "./components/bulk-assign-modal";

export default function WorkspaceDetailPage() {
  const { workspaceName } = useParams<{ workspaceName: string }>();
  const { showToast } = useToast();
  const { currentUser } = useUser();
  const isAdmin = currentUser?.is_admin ?? false;

  // Add modal state
  const [isAddUserModalOpen, setIsAddUserModalOpen] = useState(false);
  const [isAddAccountModalOpen, setIsAddAccountModalOpen] = useState(false);
  const [isAddGroupModalOpen, setIsAddGroupModalOpen] = useState(false);
  const [bulkAssignTarget, setBulkAssignTarget] = useState<"users" | "groups" | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Fetch workspace members
  const {
    workspaceUsers,
    isLoading: isUsersLoading,
    error: usersError,
    refresh: refreshUsers,
  } = useWorkspaceUsers({ workspace: workspaceName });

  const {
    workspaceGroups,
    isLoading: isGroupsLoading,
    error: groupsError,
    refresh: refreshGroups,
  } = useWorkspaceGroups({ workspace: workspaceName });

  // Fetch all available users/groups (same pattern as EntityPermissionsManager)
  const { allUsers } = useAllUsers();
  const { allServiceAccounts } = useAllServiceAccounts();
  const { allGroups } = useAllGroups();

  // Compute available options (filter out already-assigned)
  const existingUsernames = new Set(workspaceUsers.map((wu) => wu.username));
  const existingGroupNames = new Set(workspaceGroups.map((wg) => wg.group_name));

  const availableUsers = (allUsers || []).filter((u) => !existingUsernames.has(u));
  const availableAccounts = (allServiceAccounts || []).filter((u) => !existingUsernames.has(u));
  const availableGroups = (allGroups || []).filter((g) => !existingGroupNames.has(g));

  if (!workspaceName) {
    return <div>Workspace name is required.</div>;
  }

  const handleGrantUser = async (name: string, permission: PermissionLevel): Promise<boolean> => {
    try {
      await request(DYNAMIC_API_ENDPOINTS.WORKSPACE_USERS(workspaceName), {
        method: "POST",
        body: JSON.stringify({ username: name, permission }),
      });
      showToast(`Permission for ${name} has been granted`, "success");
      refreshUsers();
      return true;
    } catch {
      showToast("Failed to grant permission", "error");
      return false;
    }
  };

  const handleUpdateUser = async (name: string, permission: PermissionLevel): Promise<void> => {
    try {
      await request(DYNAMIC_API_ENDPOINTS.WORKSPACE_USER(workspaceName, name), {
        method: "PATCH",
        body: JSON.stringify({ username: name, permission }),
      });
      showToast(`Permission for ${name} has been updated`, "success");
      refreshUsers();
    } catch {
      showToast("Failed to update permission", "error");
    }
  };

  const handleRemoveUser = async (name: string): Promise<void> => {
    try {
      await request(DYNAMIC_API_ENDPOINTS.WORKSPACE_USER(workspaceName, name), {
        method: "DELETE",
      });
      showToast(`Permission for ${name} has been removed`, "success");
      refreshUsers();
    } catch {
      showToast("Failed to remove permission", "error");
    }
  };

  const handleGrantGroup = async (name: string, permission: PermissionLevel): Promise<boolean> => {
    try {
      await request(DYNAMIC_API_ENDPOINTS.WORKSPACE_GROUPS(workspaceName), {
        method: "POST",
        body: JSON.stringify({ group_name: name, permission }),
      });
      showToast(`Permission for ${name} has been granted`, "success");
      refreshGroups();
      return true;
    } catch {
      showToast("Failed to grant permission", "error");
      return false;
    }
  };

  const handleUpdateGroup = async (name: string, permission: PermissionLevel): Promise<void> => {
    try {
      await request(DYNAMIC_API_ENDPOINTS.WORKSPACE_GROUP(workspaceName, name), {
        method: "PATCH",
        body: JSON.stringify({ group_name: name, permission }),
      });
      showToast(`Permission for ${name} has been updated`, "success");
      refreshGroups();
    } catch {
      showToast("Failed to update permission", "error");
    }
  };

  const handleRemoveGroup = async (name: string): Promise<void> => {
    try {
      await request(DYNAMIC_API_ENDPOINTS.WORKSPACE_GROUP(workspaceName, name), {
        method: "DELETE",
      });
      showToast(`Permission for ${name} has been removed`, "success");
      refreshGroups();
    } catch {
      showToast("Failed to remove permission", "error");
    }
  };

  const userMembers = workspaceUsers.map((wu) => ({
    name: wu.username,
    permission: wu.permission,
  }));

  const groupMembers = workspaceGroups.map((wg) => ({
    name: wg.group_name,
    permission: wg.permission,
  }));

  return (
    <PageContainer title={`Permissions for Workspace ${workspaceName}`}>
      {/* User section action buttons */}
      <div className="flex items-center space-x-2 mb-2">
        <Button
          variant="secondary"
          onClick={() => setIsAddUserModalOpen(true)}
          disabled={availableUsers.length === 0}
          title={availableUsers.length === 0 ? "All users already have permissions" : "Add user permission"}
        >
          + Add User
        </Button>
        <Button
          variant="secondary"
          onClick={() => setIsAddAccountModalOpen(true)}
          disabled={availableAccounts.length === 0}
          title={availableAccounts.length === 0 ? "All service accounts already have permissions" : "Add service account permission"}
        >
          + Add Service Account
        </Button>
        {isAdmin && (
          <Button variant="secondary" onClick={() => setBulkAssignTarget("users")}>
            Bulk Assign Users
          </Button>
        )}
      </div>

      <WorkspaceMembersSection
        title="Users"
        members={userMembers}
        isLoading={isUsersLoading}
        error={usersError}
        onUpdate={handleUpdateUser}
        onRemove={handleRemoveUser}
        onRefresh={refreshUsers}
        nameLabel="Username"
      />

      {/* Group section action buttons */}
      <div className="flex items-center space-x-2 mb-2">
        <Button
          variant="secondary"
          onClick={() => setIsAddGroupModalOpen(true)}
          disabled={availableGroups.length === 0}
          title={availableGroups.length === 0 ? "All groups already have permissions" : "Add group permission"}
        >
          + Add Group
        </Button>
        {isAdmin && (
          <Button variant="secondary" onClick={() => setBulkAssignTarget("groups")}>
            Bulk Assign Groups
          </Button>
        )}
      </div>

      <WorkspaceMembersSection
        title="Groups"
        members={groupMembers}
        isLoading={isGroupsLoading}
        error={groupsError}
        onUpdate={handleUpdateGroup}
        onRemove={handleRemoveGroup}
        onRefresh={refreshGroups}
        nameLabel="Group Name"
      />

      {/* Grant permission modals — same pattern as EntityPermissionsManager */}
      {isAddUserModalOpen && (
        <GrantPermissionModal
          isOpen={isAddUserModalOpen}
          onClose={() => setIsAddUserModalOpen(false)}
          onSave={async (username, permission) => {
            setIsSaving(true);
            try {
              const success = await handleGrantUser(username, permission);
              if (success) setIsAddUserModalOpen(false);
            } finally {
              setIsSaving(false);
            }
          }}
          title={`Grant user permissions for workspace ${workspaceName}`}
          label="User"
          options={availableUsers}
          type="experiments"
          isLoading={isSaving}
        />
      )}

      {isAddAccountModalOpen && (
        <GrantPermissionModal
          isOpen={isAddAccountModalOpen}
          onClose={() => setIsAddAccountModalOpen(false)}
          onSave={async (username, permission) => {
            setIsSaving(true);
            try {
              const success = await handleGrantUser(username, permission);
              if (success) setIsAddAccountModalOpen(false);
            } finally {
              setIsSaving(false);
            }
          }}
          title={`Grant service account permissions for workspace ${workspaceName}`}
          label="Service Account"
          options={availableAccounts}
          type="experiments"
          isLoading={isSaving}
        />
      )}

      {isAddGroupModalOpen && (
        <GrantPermissionModal
          isOpen={isAddGroupModalOpen}
          onClose={() => setIsAddGroupModalOpen(false)}
          onSave={async (name, permission) => {
            setIsSaving(true);
            try {
              const success = await handleGrantGroup(name, permission);
              if (success) setIsAddGroupModalOpen(false);
            } finally {
              setIsSaving(false);
            }
          }}
          title={`Grant group permissions for workspace ${workspaceName}`}
          label="Group"
          options={availableGroups}
          type="experiments"
          isLoading={isSaving}
        />
      )}

      {/* Bulk assign modals — multi-select from available options */}
      <BulkAssignModal
        isOpen={bulkAssignTarget === "users"}
        onClose={() => setBulkAssignTarget(null)}
        onGrant={handleGrantUser}
        onSuccess={refreshUsers}
        title="Bulk Assign Users"
        nameLabel="Users"
        options={[...availableUsers, ...availableAccounts]}
      />
      <BulkAssignModal
        isOpen={bulkAssignTarget === "groups"}
        onClose={() => setBulkAssignTarget(null)}
        onGrant={handleGrantGroup}
        onSuccess={refreshGroups}
        title="Bulk Assign Groups"
        nameLabel="Groups"
        options={availableGroups}
      />
    </PageContainer>
  );
}
