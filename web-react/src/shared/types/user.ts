export type Group = {
  id: number;
  group_name: string;
};

export type CurrentUser = {
  display_name: string;
  groups: Group[];
  id: number;
  is_admin: boolean;
  is_service_account: boolean;
  password_expiration: string | null;
  username: string;
};

export interface UserContextType {
  currentUser: CurrentUser | null;
  setCurrentUser: (user: CurrentUser | null) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  error: Error | null;
  setError: (error: Error | null) => void;
}
