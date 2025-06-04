export interface ExperimentPermissionRequestModel {
  experiment_id: string;
  username: string;
  permission?: string;
}

export interface ModelPermissionRequestModel {
  name: string;
  username: string;
  permission?: string;
}
