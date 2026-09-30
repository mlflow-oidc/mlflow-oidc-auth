import {
  SharedPermissionsPage,
  type SharedPermissionsTab,
} from "../permissions/shared-permissions-page";

interface UserPermissionsPageProps {
  type: SharedPermissionsTab;
}

export default function UserPermissionsPage({
  type,
}: UserPermissionsPageProps) {
  return (
    <SharedPermissionsPage type={type} baseRoute="/users" entityKind="user" />
  );
}
