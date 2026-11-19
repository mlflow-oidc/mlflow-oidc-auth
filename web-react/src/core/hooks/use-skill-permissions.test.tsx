import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as useAuthModule from "./use-auth";
import type { UseAuthResult } from "./use-auth";
import * as skillService from "../services/skill-service";
import { useSkillUserPermissions } from "./use-skill-user-permissions";
import { useSkillGroupPermissions } from "./use-skill-group-permissions";
import { useUserSkillPermissions } from "./use-user-skill-permissions";
import { useGroupSkillPermissions } from "./use-group-skill-permissions";

vi.mock("./use-auth");
vi.mock("../services/skill-service");

const mockPermissions = [{ name: "user1", permission: "MANAGE", kind: "user" }];

type Case = {
  label: string;
  useRun: (value: string | null) => { permissions: unknown };
  fetcher: keyof typeof skillService;
};

const cases: Case[] = [
  {
    label: "useSkillUserPermissions",
    useRun: (name) => useSkillUserPermissions({ name }),
    fetcher: "fetchSkillUserPermissions",
  },
  {
    label: "useSkillGroupPermissions",
    useRun: (name) => useSkillGroupPermissions({ name }),
    fetcher: "fetchSkillGroupPermissions",
  },
  {
    label: "useUserSkillPermissions",
    useRun: (username) => useUserSkillPermissions({ username }),
    fetcher: "fetchUserSkillPermissions",
  },
  {
    label: "useGroupSkillPermissions",
    useRun: (groupName) => useGroupSkillPermissions({ groupName }),
    fetcher: "fetchGroupSkillPermissions",
  },
];

describe("skill permission hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
  });

  describe.each(cases)("$label", ({ useRun, fetcher }) => {
    it("fetches with the given key", async () => {
      const spy = vi
        .spyOn(skillService, fetcher)
        .mockResolvedValue(mockPermissions as never);
      const { result } = renderHook(() => useRun("@acme/reviewer"));

      await waitFor(() => {
        expect(result.current.permissions).toEqual(mockPermissions);
      });
      expect(spy).toHaveBeenCalledWith("@acme/reviewer", expect.anything());
    });

    it("does not fetch without a key", async () => {
      const spy = vi.spyOn(skillService, fetcher);
      const { result } = renderHook(() => useRun(null));

      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(spy).not.toHaveBeenCalled();
      expect(result.current.permissions).toEqual([]);
    });
  });
});
