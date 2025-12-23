import type { PromptPermission } from "../../shared/types/entity";
import { fetchUserPromptPermissions } from "../services/entity-service";
import { useApi } from "./use-api";
import { useCallback } from "react";

interface UseUserPromptPermissionsProps {
    username: string | null;
}

export function useUserPromptPermissions({
    username,
}: UseUserPromptPermissionsProps) {
    const fetcher = useCallback(
        (signal?: AbortSignal) => {
            if (username === null) {
                return Promise.resolve([]) as Promise<PromptPermission[]>;
            }
            return fetchUserPromptPermissions(username, signal);
        },
        [username]
    );

    const {
        data,
        isLoading,
        error,
        refetch: refresh,
    } = useApi<PromptPermission[]>(fetcher);

    return {
        userPromptPermissions: data ?? [],
        isLoading,
        error,
        refresh,
    };
}
