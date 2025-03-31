import { TABLE_ACTION_CONFIG } from "src/app/shared/components/table/table.config";
import { TableActionModel } from "src/app/shared/components/table/table.interface";

export const USER_COLUMN_CONFIG = [
  {
    title: "User name",
    key: "user",
  },
];

export const USER_ACTIONS: TableActionModel[] = [TABLE_ACTION_CONFIG.EDIT];
