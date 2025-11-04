import { use } from "react";
import { UserContext } from "../context/user-provider";
import type { UserContextType } from "../types/user";

export const useUserData = (): UserContextType => {
  const context = use(UserContext);

  if (context === undefined) {
    throw new Error("useUserData must be used within a UserProvider");
  }
  return context;
};
