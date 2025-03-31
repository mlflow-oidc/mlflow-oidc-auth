import { PermissionEnum } from "src/app/core/configs/permissions";

export interface PermissionsDialogData {
  entity: string;
  targetEntity: string;
  currentPermission: PermissionEnum;
}

export type PermissionDialogResultModel = PermissionEnum | null;
