import { type ReactNode } from "react";
import { useAuth } from "../hooks/use-auth";
import { useCurrentUser } from "../hooks/use-current-user";
import { UserContext } from "../hooks/use-user";

export function UserProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const userState = useCurrentUser(isAuthenticated);

  return <UserContext value={userState}>{children}</UserContext>;
}
