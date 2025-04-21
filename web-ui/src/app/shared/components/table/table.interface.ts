import { TableActionEnum } from './table.config';

export interface TableActionModel {
  icon: string;
  name: string;
  action: TableActionEnum;
}

export interface TableActionEvent<T> {
  item: T;
  action: TableActionModel;
}

export interface TableColumnConfigModel {
  title: string;
  key: string;
}
