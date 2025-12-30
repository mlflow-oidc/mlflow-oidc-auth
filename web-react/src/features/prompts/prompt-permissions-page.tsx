import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import { usePromptUserPermissions } from "../../core/hooks/use-prompt-user-permissions";
import { EntityPermissionsManager } from "../permissions/components/entity-permissions-manager";

export default function PromptPermissionsPage() {
  const { promptName } = useParams<{
    promptName: string;
  }>();

  const { isLoading, error, refresh, promptUserPermissions } =
    usePromptUserPermissions({ promptName: promptName || null });

  if (!promptName) {
    return <div>Prompt Name is required.</div>;
  }

  return (
    <PageContainer title={`Permissions for Prompt ${promptName}`}>
      <EntityPermissionsManager
        resourceId={promptName}
        resourceName={promptName}
        resourceType="prompts"
        permissions={promptUserPermissions || []}
        isLoading={isLoading}
        error={error}
        refresh={refresh}
      />
    </PageContainer>
  );
}
