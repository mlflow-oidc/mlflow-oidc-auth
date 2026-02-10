import { useRuntimeConfig } from "../../shared/context/use-runtime-config";

export type UseAuthResult = {
  isAuthenticated: boolean;
};

const useAuth = (): UseAuthResult => {
  const config = useRuntimeConfig();
  const isAuthenticated = config.authenticated;
  return {
    isAuthenticated,
  };
};

export { useAuth };
