import type { PermissionType } from "../../shared/types/entity";
import { SharedPermissionsPage } from "../permissions/shared-permissions-page";

interface GroupPermissionsPageProps {
  type: PermissionType;
}

export default function GroupPermissionsPage({ type }: GroupPermissionsPageProps) {
  return <SharedPermissionsPage type={type} baseRoute="/groups" entityKind="group" />;
}
