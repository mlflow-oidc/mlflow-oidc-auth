export interface CurrentUserModel {
  display_name: string;
  experiments: ExperimentPermission[];
  id: number;
  is_admin: boolean;
  models: RegisteredModelPermission[];
  username: string;
  prompts: PromptPermission[];
}

export interface UserModel {
  display_name?: string;
  is_admin?: boolean;
  is_service_account?: boolean;
  username: string;
}

export interface ExperimentPermission {
  id: string;
  name: string;
  permission: string;
  type: string;
}

export interface RegisteredModelPermission {
  name: string;
  permission: string;
  user_id: number;
  type: string;
}

export interface PromptPermission {
  name: string;
  permission: string;
  user_id: number;
  type: string;
}

export interface TokenModel {
  token: string;
}
