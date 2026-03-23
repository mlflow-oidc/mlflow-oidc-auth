import { useParams } from "react-router";
import { useWorkspaceUsers } from "../../core/hooks/use-workspace-users";
import { useWorkspaceGroups } from "../../core/hooks/use-workspace-groups";
import { request } from "../../core/services/api-utils";
import { DYNAMIC_API_ENDPOINTS } from "../../core/configs/api-endpoints";
import { useToast } from "../../shared/components/toast/use-toast";
import PageContainer from "../../shared/components/page/page-container";
import type { PermissionLevel } from "../../shared/types/entity";
import WorkspaceMembersSection from "./components/workspace-members-section";

export default function WorkspaceDetailPage() {
  const { workspaceName } = useParams<{ workspaceName: string }>();
  const { showToast } = useToast();

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
      <WorkspaceMembersSection
        title="Users"
        members={userMembers}
        isLoading={isUsersLoading}
        error={usersError}
        onGrant={handleGrantUser}
        onUpdate={handleUpdateUser}
        onRemove={handleRemoveUser}
        onRefresh={refreshUsers}
        nameLabel="Username"
        namePlaceholder="Enter username"
      />

      <WorkspaceMembersSection
        title="Groups"
        members={groupMembers}
        isLoading={isGroupsLoading}
        error={groupsError}
        onGrant={handleGrantGroup}
        onUpdate={handleUpdateGroup}
        onRemove={handleRemoveGroup}
        onRefresh={refreshGroups}
        nameLabel="Group Name"
        namePlaceholder="Enter group name"
      />
    </PageContainer>
  );
}
