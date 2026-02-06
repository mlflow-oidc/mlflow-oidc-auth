import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import { useGatewayEndpointUserPermissions } from "../../core/hooks/use-gateway-endpoint-user-permissions";
import { useGatewayEndpointGroupPermissions } from "../../core/hooks/use-gateway-endpoint-group-permissions";
import { EntityPermissionsManager } from "../permissions/components/entity-permissions-manager";

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

  const allPermissions = [
    ...(userPermissions || []),
    ...(groupPermissions || []),
  ];

  if (!name) {
    return <div>Endpoint Name is required.</div>;
  }

  return (
    <PageContainer title={`Permissions for Endpoint ${name}`}>
      <EntityPermissionsManager
        resourceId={name}
        resourceName={name}
        resourceType="endpoints"
        permissions={allPermissions}
        isLoading={isLoading}
        error={error}
        refresh={refresh}
      />
    </PageContainer>
  );
}
