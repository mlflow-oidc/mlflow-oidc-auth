import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import { useModelUserPermissions } from "../../core/hooks/use-model-user-permissions";
import { EntityPermissionsManager } from "../permissions/components/entity-permissions-manager";

export default function ModelPermissionsPage() {
  const { modelName } = useParams<{
    modelName: string;
  }>();

  const { isLoading, error, refresh, modelUserPermissions } =
    useModelUserPermissions({ modelName: modelName || null });

  if (!modelName) {
    return <div>Model Name is required.</div>;
  }

  return (
    <PageContainer title={`Permissions for Model ${modelName}`}>
      <EntityPermissionsManager
        resourceId={modelName}
        resourceType="models"
        permissions={modelUserPermissions || []}
        isLoading={isLoading}
        error={error}
        refresh={refresh}
      />
    </PageContainer>
  );
}
