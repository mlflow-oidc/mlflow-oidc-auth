export interface CreateServiceAccountModalData {
  title: string;
  isEditMode?: boolean;
  username?: string;
  display_name?: string;
  is_admin?: boolean;
  is_service_account?: boolean;
}

export interface CreateServiceAccountModalResult {
  username: string;
  display_name: string;
  is_admin: boolean;
  is_service_account: false;
}
