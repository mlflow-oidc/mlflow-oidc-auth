import { useParams } from "react-router";
import { useSkillUserPermissions } from "../../core/hooks/use-skill-user-permissions";
import { useSkillGroupPermissions } from "../../core/hooks/use-skill-group-permissions";
import { EntityPermissionsPageLayout } from "../permissions/components/entity-permissions-page-layout";

export default function SkillsPermissionPage() {
  // The route param arrives decoded: "@acme%2Freviewer" is the skill key "@acme/reviewer" here.
  const { name: routeName } = useParams<{
    name: string;
  }>();

  const name = routeName || null;

  const {
    isLoading: isUserLoading,
    error: userError,
    refresh: refreshUser,
    permissions: userPermissions,
  } = useSkillUserPermissions({ name });

  const {
    isLoading: isGroupLoading,
    error: groupError,
    refresh: refreshGroup,
    permissions: groupPermissions,
  } = useSkillGroupPermissions({ name });

  const isLoading = isUserLoading || isGroupLoading;
  const error = userError || groupError;
  const refresh = () => {
    refreshUser();
    refreshGroup();
  };

  if (!name) {
    return <div>Skill name is required.</div>;
  }

  return (
    <EntityPermissionsPageLayout
      title={`Permissions for Skill ${name}`}
      resourceId={name}
      resourceName={name}
      resourceType="skills"
      userPermissions={userPermissions}
      groupPermissions={groupPermissions}
      isLoading={isLoading}
      error={error}
      refresh={refresh}
    />
  );
}
