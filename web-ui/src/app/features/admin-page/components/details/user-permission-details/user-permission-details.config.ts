import { TABLE_ACTION_CONFIG } from 'src/app/shared/components/table/table.config';

export const EXPERIMENT_COLUMN_CONFIG = [
  { title: 'Experiment name', key: 'name' },
  { title: 'Permission', key: 'permission' },
  { title: 'Type', key: 'type' },
];

export const EXPERIMENT_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const EXPERIMENT_REGEX_COLUMN_CONFIG = [
  { title: 'Regex', key: 'regex' },
  { title: 'Permission', key: 'permission' },
  { title: 'Priority', key: 'priority' },
];

export const EXPERIMENT_REGEX_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const MODEL_COLUMN_CONFIG = [
  { title: 'Model name', key: 'name' },
  { title: 'Permission', key: 'permission' },
  { title: 'Type', key: 'type' },
];

export const MODEL_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const MODEL_REGEX_COLUMN_CONFIG = [
  { title: 'Regex', key: 'regex' },
  { title: 'Permission', key: 'permission' },
  { title: 'Priority', key: 'priority' },
];

export const MODEL_REGEX_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const PROMPT_COLUMN_CONFIG = [
  { title: 'Prompt name', key: 'name' },
  { title: 'Permission', key: 'permission' },
  { title: 'Type', key: 'type' },
];

export const PROMPT_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const PROMPT_REGEX_COLUMN_CONFIG = [
  { title: 'Regex', key: 'regex' },
  { title: 'Permission', key: 'permission' },
  { title: 'Priority', key: 'priority' },
];

export const PROMPT_REGEX_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];
