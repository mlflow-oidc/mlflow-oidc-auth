import { TABLE_ACTION_CONFIG } from 'src/app/shared/components/table/table.config';
import { TableActionModel } from 'src/app/shared/components/table/table.interface';

export const USER_COLUMN_CONFIG = [
  {
    title: 'User name',
    key: 'username',
  },
];

export const USER_ACTIONS: TableActionModel[] = [TABLE_ACTION_CONFIG.EDIT];

export const USER_SERVICE_ACCOUNT_ACTIONS: TableActionModel[] = [
  TABLE_ACTION_CONFIG.EDIT,
  TABLE_ACTION_CONFIG.DELETE,
  TABLE_ACTION_CONFIG.GET_ACCESS_KEY,
];
