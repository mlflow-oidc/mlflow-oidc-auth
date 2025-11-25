import { type ReactNode } from "react";
import { useAuth } from "../../features/auth/hooks/use-auth";
import { useCurrentUser } from "../../features/auth/hooks/use-current-user";
import { UserContext } from "./use-user";

export function UserProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const userState = useCurrentUser(isAuthenticated);

  return <UserContext value={userState}>{children}</UserContext>;
}
