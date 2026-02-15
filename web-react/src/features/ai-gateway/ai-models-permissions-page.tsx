import { useParams } from "react-router";
import { useGatewayModelUserPermissions } from "../../core/hooks/use-gateway-model-user-permissions";
import { useGatewayModelGroupPermissions } from "../../core/hooks/use-gateway-model-group-permissions";
import { EntityPermissionsPageLayout } from "../permissions/components/entity-permissions-page-layout";

export default function AiModelsPermissionPage() {
  const { name: routeName } = useParams<{
    name: string;
  }>();

  const name = routeName || null;

  const {
    isLoading: isUserLoading,
    error: userError,
    refresh: refreshUser,
    permissions: userPermissions,
  } = useGatewayModelUserPermissions({ name });

  const {
    isLoading: isGroupLoading,
    error: groupError,
    refresh: refreshGroup,
    permissions: groupPermissions,
  } = useGatewayModelGroupPermissions({ name });

  const isLoading = isUserLoading || isGroupLoading;
  const error = userError || groupError;
  const refresh = () => {
    refreshUser();
    refreshGroup();
  };

  if (!name) {
    return <div>AI Model Name is required.</div>;
  }

  return (
    <EntityPermissionsPageLayout
      title={`Permissions for AI Model ${name}`}
      resourceId={name}
      resourceName={name}
      resourceType="ai-models"
      userPermissions={userPermissions}
      groupPermissions={groupPermissions}
      isLoading={isLoading}
      error={error}
      refresh={refresh}
    />
  );
}
