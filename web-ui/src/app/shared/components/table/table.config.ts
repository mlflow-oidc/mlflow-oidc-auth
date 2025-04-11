import { TableActionModel } from "./table.interface";

export enum TableActionEnum {
  EDIT = "EDIT",
  DELETE = "DELETE",
  REVOKE = "REVOKE",
  ADD = "ADD",
  MANAGE = "MANAGE",
}

const ADD_ACTION: TableActionModel = {
  name: "Add",
  icon: "add",
  action: TableActionEnum.ADD,
};

const EDIT_ACTION = {
  name: "Edit",
  icon: "edit",
  action: TableActionEnum.EDIT,
};

const DELETE_ACTION = {
  name: "Delete",
  icon: "delete",
  action: TableActionEnum.DELETE,
};

const REVOKE_ACTION = {
  name: "Reset to fallback",
  icon: "key_off",
  action: TableActionEnum.REVOKE,
};

export const TABLE_ACTION_CONFIG = {
  ADD: ADD_ACTION,
  EDIT: EDIT_ACTION,
  DELETE: DELETE_ACTION,
  REVOKE: REVOKE_ACTION,
};
