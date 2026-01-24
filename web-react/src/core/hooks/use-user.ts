import { use } from "react";
import { createContext } from "react";
import type { CurrentUser } from "../../shared/types/user";

export type UserContextValue = {
  currentUser: CurrentUser | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
};

export const UserContext = createContext<UserContextValue | null>(null);

export function useUser(): UserContextValue {
  const ctx = use(UserContext);
  if (!ctx) {
    throw new Error("useUser must be used inside <UserProvider>");
  }
  return ctx;
}
