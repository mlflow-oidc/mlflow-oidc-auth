import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as useAuthModule from "./use-auth";

// Import hooks
import { useCurrentUser } from "./use-current-user";
import { useAllServiceAccounts } from "./use-all-accounts";
import { useAllExperiments } from "./use-all-experiments";
import { useAllGroups } from "./use-all-groups";
import { useAllModels } from "./use-all-models";
import { useAllPrompts } from "./use-all-prompts";
import { useAllUsers } from "./use-all-users";
import { useDeletedExperiments } from "./use-deleted-experiments";
import { useDeletedRuns } from "./use-deleted-runs";
import { useUserDetails } from "./use-user-details";

// Import fetchers to mock
import * as userService from "../services/user-service";
import * as entityService from "../services/entity-service";
import * as trashService from "../services/trash-service";

vi.mock("./use-auth");
vi.mock("../services/user-service");
vi.mock("../services/entity-service");
vi.mock("../services/trash-service");

describe("Core Data Hooks", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.spyOn(useAuthModule, "useAuth").mockReturnValue({ isAuthenticated: true } as any);
    });

    describe("useCurrentUser", () => {
        it("returns current user data", async () => {
            const mockUser = { username: "testuser", is_admin: true };
            vi.spyOn(userService, "fetchCurrentUser").mockResolvedValue(mockUser as any);

            const { result } = renderHook(() => useCurrentUser());

            await waitFor(() => {
                expect(result.current.currentUser).toEqual(mockUser);
            });
        });
    });

    describe("useAllServiceAccounts", () => {
        it("returns all service accounts", async () => {
            const mockAccounts = ["sa1", "sa2"];
            vi.spyOn(userService, "fetchAllServiceAccounts").mockResolvedValue(mockAccounts);

            const { result } = renderHook(() => useAllServiceAccounts());

            await waitFor(() => {
                expect(result.current.allServiceAccounts).toEqual(mockAccounts);
            });
        });
    });

    describe("useAllExperiments", () => {
        it("returns all experiments", async () => {
            const mockExperiments = [{ id: "1", name: "exp1" }];
            vi.spyOn(entityService, "fetchAllExperiments").mockResolvedValue(mockExperiments as any);

            const { result } = renderHook(() => useAllExperiments());

            await waitFor(() => {
                expect(result.current.allExperiments).toEqual(mockExperiments);
            });
        });
    });

    describe("useAllGroups", () => {
        it("returns all groups", async () => {
            const mockGroups = ["group1", "group2"];
            vi.spyOn(entityService, "fetchAllGroups").mockResolvedValue(mockGroups);

            const { result } = renderHook(() => useAllGroups());

            await waitFor(() => {
                expect(result.current.allGroups).toEqual(mockGroups);
            });
        });
    });

    describe("useAllModels", () => {
        it("returns all models", async () => {
            const mockModels = [{ id: "1", name: "model1" }];
            vi.spyOn(entityService, "fetchAllModels").mockResolvedValue(mockModels as any);

            const { result } = renderHook(() => useAllModels());

            await waitFor(() => {
                expect(result.current.allModels).toEqual(mockModels);
            });
        });
    });

    describe("useAllPrompts", () => {
        it("returns all prompts", async () => {
            const mockPrompts = [{ id: "1", name: "prompt1" }];
            vi.spyOn(entityService, "fetchAllPrompts").mockResolvedValue(mockPrompts as any);

            const { result } = renderHook(() => useAllPrompts());

            await waitFor(() => {
                expect(result.current.allPrompts).toEqual(mockPrompts);
            });
        });
    });

    describe("useAllUsers", () => {
        it("returns all users", async () => {
            const mockUsers = ["user1", "user2"];
            vi.spyOn(userService, "fetchAllUsers").mockResolvedValue(mockUsers);

            const { result } = renderHook(() => useAllUsers());

            await waitFor(() => {
                expect(result.current.allUsers).toEqual(mockUsers);
            });
        });
    });

    describe("useDeletedExperiments", () => {
        it("returns deleted experiments", async () => {
            const mockDeleted = { deleted_experiments: [{ id: "1", name: "deleted_exp1" }] };
            vi.spyOn(trashService, "fetchDeletedExperiments").mockResolvedValue(mockDeleted as any);

            const { result } = renderHook(() => useDeletedExperiments());

            await waitFor(() => {
                expect(result.current.deletedExperiments).toEqual(mockDeleted.deleted_experiments);
            });
        });
    });

    describe("useDeletedRuns", () => {
        it("returns deleted runs", async () => {
            const mockDeleted = { deleted_runs: [{ id: "1", run_uuid: "run1" }] };
            vi.spyOn(trashService, "fetchDeletedRuns").mockResolvedValue(mockDeleted as any);

            const { result } = renderHook(() => useDeletedRuns());

            await waitFor(() => {
                expect(result.current.deletedRuns).toEqual(mockDeleted.deleted_runs);
            });
        });
    });

    describe("useUserDetails", () => {
        it("returns user details when username is provided", async () => {
            const mockUser = { username: "user1", is_admin: false };
            vi.spyOn(userService, "fetchUserDetails").mockResolvedValue(mockUser as any);

            const { result } = renderHook(() => useUserDetails({ username: "user1" }));

            await waitFor(() => {
                expect(result.current.user).toEqual(mockUser);
            });
        });

        it("does not fetch when username is null", async () => {
            const spy = vi.spyOn(userService, "fetchUserDetails");
            renderHook(() => useUserDetails({ username: null }));
            // Wait a tick to ensure no async actions were triggered
            await new Promise(resolve => setTimeout(resolve, 0));
            expect(spy).not.toHaveBeenCalled();
        });
    });
});
