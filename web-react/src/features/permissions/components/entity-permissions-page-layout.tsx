import PageContainer from "../../../shared/components/page/page-container";
import { EntityPermissionsManager } from "./entity-permissions-manager";
import type {
  EntityPermission,
  PermissionType,
} from "../../../shared/types/entity";

interface EntityPermissionsPageLayoutProps {
  title: string;
  resourceId: string;
  resourceName: string;
  resourceType: PermissionType;
  userPermissions?: EntityPermission[];
  groupPermissions?: EntityPermission[];
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
}

export function EntityPermissionsPageLayout({
  title,
  resourceId,
  resourceName,
  resourceType,
  userPermissions,
  groupPermissions,
  isLoading,
  error,
  refresh,
}: EntityPermissionsPageLayoutProps) {
  const allPermissions = [
    ...(userPermissions || []),
    ...(groupPermissions || []),
  ];

  return (
    <PageContainer title={title}>
      <EntityPermissionsManager
        resourceId={resourceId}
        resourceName={resourceName}
        resourceType={resourceType}
        permissions={allPermissions}
        isLoading={isLoading}
        error={error}
        refresh={refresh}
      />
    </PageContainer>
  );
}
