import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import { usePromptUserPermissions } from "../../core/hooks/use-prompt-user-permissions";
import { usePromptGroupPermissions } from "../../core/hooks/use-prompt-group-permissions";
import { EntityPermissionsManager } from "../permissions/components/entity-permissions-manager";

export default function PromptPermissionsPage() {
  const { promptName } = useParams<{
    promptName: string;
  }>();

  const {
    isLoading: isUserLoading,
    error: userError,
    refresh: refreshUser,
    promptUserPermissions,
  } = usePromptUserPermissions({ promptName: promptName || null });

  const {
    isLoading: isGroupLoading,
    error: groupError,
    refresh: refreshGroup,
    promptGroupPermissions,
  } = usePromptGroupPermissions({ promptName: promptName || null });

  const isLoading = isUserLoading || isGroupLoading;
  const error = userError || groupError;
  const refresh = () => {
    refreshUser();
    refreshGroup();
  };

  const allPermissions = [
    ...(promptUserPermissions || []),
    ...(promptGroupPermissions || []),
  ];

  if (!promptName) {
    return <div>Prompt Name is required.</div>;
  }

  return (
    <PageContainer title={`Permissions for Prompt ${promptName}`}>
      <EntityPermissionsManager
        resourceId={promptName}
        resourceName={promptName}
        resourceType="prompts"
        permissions={allPermissions}
        isLoading={isLoading}
        error={error}
        refresh={refresh}
      />
    </PageContainer>
  );
}
