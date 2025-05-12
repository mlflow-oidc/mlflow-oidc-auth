import { TABLE_ACTION_CONFIG } from 'src/app/shared/components/table/table.config';

export const EXPERIMENT_COLUMN_CONFIG = [
  { title: 'Experiment name', key: 'name' },
  { title: 'Permission', key: 'permission' },
];

export const EXPERIMENT_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const EXPERIMENT_REGEX_COLUMN_CONFIG = [
  { title: 'Regex', key: 'regex' },
  { title: 'Permission', key: 'permission' },
  { title: 'Priority', key: 'priority' },
];

export const EXPERIMENT_REGEX_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const MODELS_COLUMN_CONFIG = [
  { title: 'Model name', key: 'name' },
  { title: 'Permission', key: 'permission' },
];

export const MODELS_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const MODELS_REGEX_COLUMN_CONFIG = [
  { title: 'Regex', key: 'regex' },
  { title: 'Permission', key: 'permission' },
  { title: 'Priority', key: 'priority' },
];

export const MODELS_REGEX_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const PROMPTS_COLUMN_CONFIG = [
  { title: 'Prompt name', key: 'name' },
  { title: 'Permission', key: 'permission' },
];

export const PROMPTS_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];

export const PROMPTS_REGEX_COLUMN_CONFIG = [
  { title: 'Regex', key: 'regex' },
  { title: 'Permission', key: 'permission' },
  { title: 'Priority', key: 'priority' },
];

export const PROMPTS_REGEX_ACTIONS = [TABLE_ACTION_CONFIG.EDIT, TABLE_ACTION_CONFIG.REVOKE];
