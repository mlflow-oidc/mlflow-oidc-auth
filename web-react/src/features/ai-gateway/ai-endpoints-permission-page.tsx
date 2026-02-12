import { useParams } from "react-router";
import { useGatewayEndpointUserPermissions } from "../../core/hooks/use-gateway-endpoint-user-permissions";
import { useGatewayEndpointGroupPermissions } from "../../core/hooks/use-gateway-endpoint-group-permissions";
import { EntityPermissionsPageLayout } from "../permissions/components/entity-permissions-page-layout";

export default function AiEndpointsPermissionPage() {
  const { name: routeName } = useParams<{
    name: string;
  }>();

  const name = routeName || null;

  const {
    isLoading: isUserLoading,
    error: userError,
    refresh: refreshUser,
    permissions: userPermissions,
  } = useGatewayEndpointUserPermissions({ name });

  const {
    isLoading: isGroupLoading,
    error: groupError,
    refresh: refreshGroup,
    permissions: groupPermissions,
  } = useGatewayEndpointGroupPermissions({ name });

  const isLoading = isUserLoading || isGroupLoading;
  const error = userError || groupError;
  const refresh = () => {
    refreshUser();
    refreshGroup();
  };

  if (!name) {
    return <div>Endpoint Name is required.</div>;
  }

  return (
    <EntityPermissionsPageLayout
      title={`Permissions for Endpoint ${name}`}
      resourceId={name}
      resourceName={name}
      resourceType="endpoints"
      userPermissions={userPermissions}
      groupPermissions={groupPermissions}
      isLoading={isLoading}
      error={error}
      refresh={refresh}
    />
  );
}
