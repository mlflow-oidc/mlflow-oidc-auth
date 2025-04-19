export interface CreateExperimentPermissionRequestBodyModel {
  experiment_name?: string;
  experiment_id?: string;
  username: string;
  permission: string;
}

export interface CreateModelPermissionRequestBodyModel {
  name: string;
  username: string;
  permission: string;
}
