import {
  SharedPermissionsPage,
  type SharedPermissionsTab,
} from "../permissions/shared-permissions-page";

interface ServiceAccountPermissionPageProps {
  type: SharedPermissionsTab;
}

export default function ServiceAccountPermissionPage({
  type,
}: ServiceAccountPermissionPageProps) {
  return (
    <SharedPermissionsPage
      type={type}
      baseRoute="/service-accounts"
      entityKind="user"
    />
  );
}
