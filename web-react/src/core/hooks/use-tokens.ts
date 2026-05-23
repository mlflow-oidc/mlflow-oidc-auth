import { useApi } from "./use-api";
import {
  fetchUserTokens,
  type UserToken,
  type UserTokenListResponse,
} from "../services/token-service";

export function useTokens() {
  const {
    data: tokenResponse,
    isLoading,
    error,
    refetch: refresh,
  } = useApi<UserTokenListResponse>(fetchUserTokens);

  const tokens: UserToken[] = tokenResponse?.tokens ?? [];

  return { tokens, isLoading, error, refresh };
}
