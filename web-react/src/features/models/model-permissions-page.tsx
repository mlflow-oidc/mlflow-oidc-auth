import { useParams } from "react-router";
import { useModelUserPermissions } from "../../core/hooks/use-model-user-permissions";
import { useModelGroupPermissions } from "../../core/hooks/use-model-group-permissions";
import { EntityPermissionsPageLayout } from "../permissions/components/entity-permissions-page-layout";

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

  if (!modelName) {
    return <div>Model Name is required.</div>;
  }

  return (
    <EntityPermissionsPageLayout
      title={`Permissions for Model ${modelName}`}
      resourceId={modelName}
      resourceName={modelName}
      resourceType="models"
      userPermissions={modelUserPermissions}
      groupPermissions={modelGroupPermissions}
      isLoading={isLoading}
      error={error}
      refresh={refresh}
    />
  );
}
