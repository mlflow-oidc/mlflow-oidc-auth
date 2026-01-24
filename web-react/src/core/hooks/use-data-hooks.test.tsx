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

// Import types
import type { CurrentUser } from "../../shared/types/user";
import type {
  ExperimentListItem,
  ModelListItem,
  DeletedExperiment,
  DeletedRun,
} from "../../shared/types/entity";

vi.mock("./use-auth");
vi.mock("../services/user-service");
vi.mock("../services/entity-service");
vi.mock("../services/trash-service");

describe("Core Data Hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    });
  });

  describe("useCurrentUser", () => {
    it("returns current user data", async () => {
      const mockUser: CurrentUser = {
        username: "testuser",
        is_admin: true,
        display_name: "Test User",
        groups: [],
        id: 1,
        is_service_account: false,
        password_expiration: null,
      };
      vi.spyOn(userService, "fetchCurrentUser").mockResolvedValue(mockUser);

      const { result } = renderHook(() => useCurrentUser());

      await waitFor(() => {
        expect(result.current.currentUser).toEqual(mockUser);
      });
    });
  });

  describe("useAllServiceAccounts", () => {
    it("returns all service accounts", async () => {
      const mockAccounts = ["sa1", "sa2"];
      vi.spyOn(userService, "fetchAllServiceAccounts").mockResolvedValue(
        mockAccounts,
      );

      const { result } = renderHook(() => useAllServiceAccounts());

      await waitFor(() => {
        expect(result.current.allServiceAccounts).toEqual(mockAccounts);
      });
    });
  });

  describe("useAllExperiments", () => {
    it("returns all experiments", async () => {
      const mockExperiments: ExperimentListItem[] = [
        { id: "1", name: "exp1", tags: {} },
      ];
      vi.spyOn(entityService, "fetchAllExperiments").mockResolvedValue(
        mockExperiments,
      );

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
      const mockModels: ModelListItem[] = [
        { name: "model1", aliases: "", description: "", tags: {} },
      ];
      vi.spyOn(entityService, "fetchAllModels").mockResolvedValue(mockModels);

      const { result } = renderHook(() => useAllModels());

      await waitFor(() => {
        expect(result.current.allModels).toEqual(mockModels);
      });
    });
  });

  describe("useAllPrompts", () => {
    it("returns all prompts", async () => {
      const mockPrompts: ModelListItem[] = [
        { name: "prompt1", aliases: "", description: "", tags: {} },
      ];
      vi.spyOn(entityService, "fetchAllPrompts").mockResolvedValue(mockPrompts);

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
      const mockDeleted = {
        deleted_experiments: [
          {
            experiment_id: "1",
            name: "deleted_exp1",
            lifecycle_stage: "deleted",
            artifact_location: "",
            tags: {},
            creation_time: 0,
            last_update_time: 0,
          } as DeletedExperiment,
        ],
      };
      vi.spyOn(trashService, "fetchDeletedExperiments").mockResolvedValue(
        mockDeleted,
      );

      const { result } = renderHook(() => useDeletedExperiments());

      await waitFor(() => {
        expect(result.current.deletedExperiments).toEqual(
          mockDeleted.deleted_experiments,
        );
      });
    });
  });

  describe("useDeletedRuns", () => {
    it("returns deleted runs", async () => {
      const mockDeleted = {
        deleted_runs: [
          {
            run_id: "run1",
            experiment_id: "1",
            run_name: "run1",
            status: "FINISHED",
            start_time: 0,
            end_time: null,
            lifecycle_stage: "deleted",
          } as DeletedRun,
        ],
      };
      vi.spyOn(trashService, "fetchDeletedRuns").mockResolvedValue(mockDeleted);

      const { result } = renderHook(() => useDeletedRuns());

      await waitFor(() => {
        expect(result.current.deletedRuns).toEqual(mockDeleted.deleted_runs);
      });
    });
  });

  describe("useUserDetails", () => {
    it("returns user details when username is provided", async () => {
      const mockUser: CurrentUser = {
        username: "user1",
        is_admin: false,
        display_name: "User 1",
        groups: [],
        id: 2,
        is_service_account: false,
        password_expiration: null,
      };
      vi.spyOn(userService, "fetchUserDetails").mockResolvedValue(mockUser);

      const { result } = renderHook(() =>
        useUserDetails({ username: "user1" }),
      );

      await waitFor(() => {
        expect(result.current.user).toEqual(mockUser);
      });
    });

    it("does not fetch when username is null", async () => {
      const spy = vi.spyOn(userService, "fetchUserDetails");
      renderHook(() => useUserDetails({ username: null }));
      // Wait a tick to ensure no async actions were triggered
      await new Promise((resolve) => setTimeout(resolve, 0));
      expect(spy).not.toHaveBeenCalled();
    });
  });
});
