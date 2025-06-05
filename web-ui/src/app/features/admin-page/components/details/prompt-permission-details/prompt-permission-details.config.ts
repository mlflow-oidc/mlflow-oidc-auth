import { TABLE_ACTION_CONFIG } from 'src/app/shared/components/table/table.config';

export const TABLE_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const COLUMN_CONFIG = [
  {
    title: 'User name',
    key: 'username',
  },
  {
    title: 'Permissions',
    key: 'permission',
  },
  {
    title: 'Kind',
    key: 'kind',
  },
];
