import { TABLE_ACTION_CONFIG } from 'src/app/shared/components/table/table.config';
import { TableActionModel } from 'src/app/shared/components/table/table.interface';

export const GROUP_COLUMN_CONFIG = [
  {
    title: 'Group name',
    key: 'group',
  },
];

export const GROUP_ACTIONS: TableActionModel[] = [TABLE_ACTION_CONFIG.EDIT];
