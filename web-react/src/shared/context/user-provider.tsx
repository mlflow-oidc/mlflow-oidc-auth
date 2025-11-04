import React, {
  createContext,
  useState,
  useEffect,
  useMemo,
  type ReactNode,
} from "react";

import type { CurrentUser, UserContextType } from "../types/user";
import { fetchCurrentUser } from "../../features/auth/services/auth-service";

const UserContext = createContext<UserContextType | undefined>(undefined);

interface UserProviderProps {
  children: ReactNode;
}

export const UserProvider: React.FC<UserProviderProps> = ({ children }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    async function loadCurrentUser() {
      setIsLoading(true);
      setError(null);
      try {
        const user = await fetchCurrentUser(abortController.signal);
        setCurrentUser(user);
      } catch (err) {
        if (!abortController.signal.aborted) {
          console.error("UserProvider: failed to load user info", err);
          setError(err as Error);
          setCurrentUser(null);
        }
      } finally {
        if (!abortController.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    void loadCurrentUser();

    return () => {
      abortController.abort();
    };
  }, []);

  const contextValue = useMemo(
    () => ({
      currentUser,
      isLoading,
      error,
    }),
    [currentUser, isLoading, error]
  );

  return <UserContext value={contextValue}>{children}</UserContext>;
};

export { UserContext };
