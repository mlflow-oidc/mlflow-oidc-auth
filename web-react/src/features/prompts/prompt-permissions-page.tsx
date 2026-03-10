import { useParams } from "react-router";
import { usePromptUserPermissions } from "../../core/hooks/use-prompt-user-permissions";
import { usePromptGroupPermissions } from "../../core/hooks/use-prompt-group-permissions";
import { EntityPermissionsPageLayout } from "../permissions/components/entity-permissions-page-layout";

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

  if (!promptName) {
    return <div>Prompt Name is required.</div>;
  }

  return (
    <EntityPermissionsPageLayout
      title={`Permissions for Prompt ${promptName}`}
      resourceId={promptName}
      resourceName={promptName}
      resourceType="prompts"
      userPermissions={promptUserPermissions}
      groupPermissions={promptGroupPermissions}
      isLoading={isLoading}
      error={error}
      refresh={refresh}
    />
  );
}
