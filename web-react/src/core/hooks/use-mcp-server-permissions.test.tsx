import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as useAuthModule from "./use-auth";
import type { UseAuthResult } from "./use-auth";
import * as mcpServerService from "../services/mcp-server-service";
import { useMcpServerUserPermissions } from "./use-mcp-server-user-permissions";
import { useMcpServerGroupPermissions } from "./use-mcp-server-group-permissions";
import { useUserMcpServerPermissions } from "./use-user-mcp-server-permissions";
import { useGroupMcpServerPermissions } from "./use-group-mcp-server-permissions";

vi.mock("./use-auth");
vi.mock("../services/mcp-server-service");

const mockPermissions = [{ name: "user1", permission: "MANAGE", kind: "user" }];

type Case = {
  label: string;
  useRun: (value: string | null) => { permissions: unknown };
  fetcher: keyof typeof mcpServerService;
};

const cases: Case[] = [
  {
    label: "useMcpServerUserPermissions",
    useRun: (name) => useMcpServerUserPermissions({ name }),
    fetcher: "fetchMcpServerUserPermissions",
  },
  {
    label: "useMcpServerGroupPermissions",
    useRun: (name) => useMcpServerGroupPermissions({ name }),
    fetcher: "fetchMcpServerGroupPermissions",
  },
  {
    label: "useUserMcpServerPermissions",
    useRun: (username) => useUserMcpServerPermissions({ username }),
    fetcher: "fetchUserMcpServerPermissions",
  },
  {
    label: "useGroupMcpServerPermissions",
    useRun: (groupName) => useGroupMcpServerPermissions({ groupName }),
    fetcher: "fetchGroupMcpServerPermissions",
  },
];

describe("MCP server permission hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
  });

  describe.each(cases)("$label", ({ useRun, fetcher }) => {
    it("fetches with the given key", async () => {
      const spy = vi
        .spyOn(mcpServerService, fetcher)
        .mockResolvedValue(mockPermissions as never);
      const { result } = renderHook(() => useRun("com.example/weather"));

      await waitFor(() => {
        expect(result.current.permissions).toEqual(mockPermissions);
      });
      expect(spy).toHaveBeenCalledWith("com.example/weather", expect.anything());
    });

    it("does not fetch without a key", async () => {
      const spy = vi.spyOn(mcpServerService, fetcher);
      const { result } = renderHook(() => useRun(null));

      await new Promise((resolve) => setTimeout(resolve, 10));
      expect(spy).not.toHaveBeenCalled();
      expect(result.current.permissions).toEqual([]);
    });
  });
});
