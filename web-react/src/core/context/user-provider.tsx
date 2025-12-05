import { type ReactNode } from "react";
import { useCurrentUser } from "../hooks/use-current-user";
import { UserContext } from "../hooks/use-user";

export function UserProvider({ children }: { children: ReactNode }) {
  const userState = useCurrentUser();

  return <UserContext value={userState}>{children}</UserContext>;
}
