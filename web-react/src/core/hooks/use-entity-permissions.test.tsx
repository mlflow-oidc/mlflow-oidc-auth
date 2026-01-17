import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as useAuthModule from "./use-auth";

// Import hooks
import { useExperimentUserPermissions } from "./use-experiment-user-permissions";
import { useExperimentGroupPermissions } from "./use-experiment-group-permissions";
import { useModelUserPermissions } from "./use-model-user-permissions";
import { useModelGroupPermissions } from "./use-model-group-permissions";
import { usePromptUserPermissions } from "./use-prompt-user-permissions";
import { usePromptGroupPermissions } from "./use-prompt-group-permissions";
import { useUserExperimentPermissions } from "./use-user-experiment-permissions";
import { useUserRegisteredModelPermissions } from "./use-user-model-permissions";
import { useUserPromptPermissions } from "./use-user-prompt-permissions";
import { useGroupExperimentPermissions } from "./use-group-experiment-permissions";
import { useGroupRegisteredModelPermissions } from "./use-group-model-permissions";
import { useGroupPromptPermissions } from "./use-group-prompt-permissions";

import { useUserExperimentPatternPermissions } from "./use-user-experiment-pattern-permissions";
import { useUserModelPatternPermissions } from "./use-user-model-pattern-permissions";
import { useUserPromptPatternPermissions } from "./use-user-prompt-pattern-permissions";
import { useGroupExperimentPatternPermissions } from "./use-group-experiment-pattern-permissions";
import { useGroupModelPatternPermissions } from "./use-group-model-pattern-permissions";
import { useGroupPromptPatternPermissions } from "./use-group-prompt-pattern-permissions";

// Import fetchers to mock
import * as entityService from "../services/entity-service";

vi.mock("./use-auth");
vi.mock("../services/entity-service");

const mockPermissions = [{ principal: "user1", permission: "MANAGE" }];

describe("Entity and Pattern Permission Hooks", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.spyOn(useAuthModule, "useAuth").mockReturnValue({ isAuthenticated: true } as any);
    });

    const testHook = (hook: any, props: any, fetcherName: string) => {
        if (!hook) {
            console.error(`Hook for fetcher ${fetcherName} is undefined!`);
            return;
        }

        describe(hook.name || fetcherName, () => {
            it(`fetches data for ${fetcherName} when props provided`, async () => {
                const spy = vi.spyOn(entityService, fetcherName as any).mockResolvedValue(mockPermissions as any);
                const { result } = renderHook(() => hook(props));
                
                await waitFor(() => {
                    // Find either 'permissions' or something ending with 'Permissions'
                    const key = Object.keys(result.current).find(k => k === "permissions" || k.endsWith("Permissions"));
                    expect(result.current[key as any]).toEqual(mockPermissions);
                });
                expect(spy).toHaveBeenCalled();
            });

            it(`does not fetch for ${fetcherName} when props are null`, async () => {
                const spy = vi.spyOn(entityService, fetcherName as any);
                const nullProps = Object.keys(props).reduce((acc: any, key) => ({ ...acc, [key]: null }), {});
                renderHook(() => hook(nullProps));
                
                await new Promise(resolve => setTimeout(resolve, 10));
                expect(spy).not.toHaveBeenCalled();
            });
        });
    };

    // Experiment/Model/Prompt Entity Permissions
    testHook(useExperimentUserPermissions, { experimentId: "exp1" }, "fetchExperimentUserPermissions");
    testHook(useExperimentGroupPermissions, { experimentId: "exp1" }, "fetchExperimentGroupPermissions");
    testHook(useModelUserPermissions, { modelName: "model1" }, "fetchModelUserPermissions");
    testHook(useModelGroupPermissions, { modelName: "model1" }, "fetchModelGroupPermissions");
    testHook(usePromptUserPermissions, { promptName: "prompt1" }, "fetchPromptUserPermissions");
    testHook(usePromptGroupPermissions, { promptName: "prompt1" }, "fetchPromptGroupPermissions");
    
    // User Permissions
    testHook(useUserExperimentPermissions, { username: "user1" }, "fetchUserExperimentPermissions");
    testHook(useUserRegisteredModelPermissions, { username: "user1" }, "fetchUserRegisteredModelPermissions");
    testHook(useUserPromptPermissions, { username: "user1" }, "fetchUserPromptPermissions");
    
    // Group Permissions
    testHook(useGroupExperimentPermissions, { groupName: "group1" }, "fetchGroupExperimentPermissions");
    testHook(useGroupRegisteredModelPermissions, { groupName: "group1" }, "fetchGroupRegisteredModelPermissions");
    testHook(useGroupPromptPermissions, { groupName: "group1" }, "fetchGroupPromptPermissions");

    // Pattern Permissions
    testHook(useUserExperimentPatternPermissions, { username: "user1" }, "fetchUserExperimentPatternPermissions");
    testHook(useUserModelPatternPermissions, { username: "user1" }, "fetchUserModelPatternPermissions");
    testHook(useUserPromptPatternPermissions, { username: "user1" }, "fetchUserPromptPatternPermissions");
    testHook(useGroupExperimentPatternPermissions, { groupName: "group1" }, "fetchGroupExperimentPatternPermissions");
    testHook(useGroupModelPatternPermissions, { groupName: "group1" }, "fetchGroupModelPatternPermissions");
    testHook(useGroupPromptPatternPermissions, { groupName: "group1" }, "fetchGroupPromptPatternPermissions");
});
