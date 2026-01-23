import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import { useModelUserPermissions } from "../../core/hooks/use-model-user-permissions";
import { useModelGroupPermissions } from "../../core/hooks/use-model-group-permissions";
import { EntityPermissionsManager } from "../permissions/components/entity-permissions-manager";

export default function ModelPermissionsPage() {
  const { modelName } = useParams<{
    modelName: string;
  }>();

  const {
    isLoading: isUserLoading,
    error: userError,
    refresh: refreshUser,
    modelUserPermissions,
  } = useModelUserPermissions({ modelName: modelName || null });

  const {
    isLoading: isGroupLoading,
    error: groupError,
    refresh: refreshGroup,
    modelGroupPermissions,
  } = useModelGroupPermissions({ modelName: modelName || null });

  const isLoading = isUserLoading || isGroupLoading;
  const error = userError || groupError;
  const refresh = () => {
    refreshUser();
    refreshGroup();
  };

  const allPermissions = [
    ...(modelUserPermissions || []),
    ...(modelGroupPermissions || []),
  ];

  if (!modelName) {
    return <div>Model Name is required.</div>;
  }

  return (
    <PageContainer title={`Permissions for Model ${modelName}`}>
      <EntityPermissionsManager
        resourceId={modelName}
        resourceName={modelName}
        resourceType="models"
        permissions={allPermissions}
        isLoading={isLoading}
        error={error}
        refresh={refresh}
      />
    </PageContainer>
  );
}
