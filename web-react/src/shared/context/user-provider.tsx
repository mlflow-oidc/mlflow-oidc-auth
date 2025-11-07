import React, { createContext, useState, useMemo, type ReactNode } from "react";

import type { CurrentUser, UserContextType } from "../types/user";

const initialContext: UserContextType = {
  currentUser: null,
  setCurrentUser: () => {},
  isLoading: false,
  setIsLoading: () => {},
  error: null,
  setError: () => {},
};

const UserContext = createContext<UserContextType>(initialContext);

interface UserProviderProps {
  children: ReactNode;
}

export const UserProvider: React.FC<UserProviderProps> = ({ children }) => {
  const [isLoading, setIsLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState<Error | null>(null);

  const contextValue = useMemo(
    () => ({
      currentUser,
      setCurrentUser,
      isLoading,
      setIsLoading,
      error,
      setError,
    }),
    [currentUser, isLoading, error]
  );

  return <UserContext value={contextValue}>{children}</UserContext>;
};

export { UserContext };
