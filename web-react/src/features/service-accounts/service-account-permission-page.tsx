import type { PermissionType } from "../../shared/types/entity";
import { SharedPermissionsPage } from "../permissions/shared-permissions-page";

interface ServiceAccountPermissionPageProps {
  type: PermissionType;
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
