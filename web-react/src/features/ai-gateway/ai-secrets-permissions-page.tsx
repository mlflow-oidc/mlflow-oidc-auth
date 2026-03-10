import { useParams } from "react-router";
import { useGatewaySecretUserPermissions } from "../../core/hooks/use-gateway-secret-user-permissions";
import { useGatewaySecretGroupPermissions } from "../../core/hooks/use-gateway-secret-group-permissions";
import { EntityPermissionsPageLayout } from "../permissions/components/entity-permissions-page-layout";

export default function AiSecretsPermissionPage() {
  const { name: routeKey } = useParams<{
    name: string;
  }>();

  const key = routeKey || null;

  const {
    isLoading: isUserLoading,
    error: userError,
    refresh: refreshUser,
    permissions: userPermissions,
  } = useGatewaySecretUserPermissions({ name: key });

  const {
    isLoading: isGroupLoading,
    error: groupError,
    refresh: refreshGroup,
    permissions: groupPermissions,
  } = useGatewaySecretGroupPermissions({ name: key });

  const isLoading = isUserLoading || isGroupLoading;
  const error = userError || groupError;
  const refresh = () => {
    refreshUser();
    refreshGroup();
  };

  if (!key) {
    return <div>Secret Key is required.</div>;
  }

  return (
    <EntityPermissionsPageLayout
      title={`Permissions for Secret ${key}`}
      resourceId={key}
      resourceName={key}
      resourceType="ai-secrets"
      userPermissions={userPermissions}
      groupPermissions={groupPermissions}
      isLoading={isLoading}
      error={error}
      refresh={refresh}
    />
  );
}
