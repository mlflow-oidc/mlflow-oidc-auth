import { useParams } from "react-router";
import { useMcpServerUserPermissions } from "../../core/hooks/use-mcp-server-user-permissions";
import { useMcpServerGroupPermissions } from "../../core/hooks/use-mcp-server-group-permissions";
import { EntityPermissionsPageLayout } from "../permissions/components/entity-permissions-page-layout";

export default function McpServersPermissionPage() {
  // The route param arrives decoded: "com.example%2Fweather" is "com.example/weather" here.
  const { name: routeName } = useParams<{
    name: string;
  }>();

  const name = routeName || null;

  const {
    isLoading: isUserLoading,
    error: userError,
    refresh: refreshUser,
    permissions: userPermissions,
  } = useMcpServerUserPermissions({ name });

  const {
    isLoading: isGroupLoading,
    error: groupError,
    refresh: refreshGroup,
    permissions: groupPermissions,
  } = useMcpServerGroupPermissions({ name });

  const isLoading = isUserLoading || isGroupLoading;
  const error = userError || groupError;
  const refresh = () => {
    refreshUser();
    refreshGroup();
  };

  if (!name) {
    return <div>MCP server name is required.</div>;
  }

  return (
    <EntityPermissionsPageLayout
      title={`Permissions for MCP Server ${name}`}
      resourceId={name}
      resourceName={name}
      resourceType="mcp-servers"
      userPermissions={userPermissions}
      groupPermissions={groupPermissions}
      isLoading={isLoading}
      error={error}
      refresh={refresh}
    />
  );
}
