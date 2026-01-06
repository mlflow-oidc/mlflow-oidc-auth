import type { PermissionType } from "../../shared/types/entity";
import { SharedPermissionsPage } from "../permissions/shared-permissions-page";

interface UserPermissionsPageProps {
  type: PermissionType;
}

export default function UserPermissionsPage({ type }: UserPermissionsPageProps) {
  return <SharedPermissionsPage type={type} baseRoute="/users" entityKind="user" />;
}
