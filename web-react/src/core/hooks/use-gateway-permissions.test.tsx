import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import * as useAuthModule from "./use-auth";

// Resource-scoped hooks (param: name)
import { useGatewayEndpointUserPermissions } from "./use-gateway-endpoint-user-permissions";
import { useGatewayEndpointGroupPermissions } from "./use-gateway-endpoint-group-permissions";
import { useGatewaySecretUserPermissions } from "./use-gateway-secret-user-permissions";
import { useGatewaySecretGroupPermissions } from "./use-gateway-secret-group-permissions";
import { useGatewayModelUserPermissions } from "./use-gateway-model-user-permissions";
import { useGatewayModelGroupPermissions } from "./use-gateway-model-group-permissions";

// User-scoped hooks (param: username)
import { useUserGatewayEndpointPermissions } from "./use-user-gateway-endpoint-permissions";
import { useUserGatewaySecretPermissions } from "./use-user-gateway-secret-permissions";
import { useUserGatewayModelPermissions } from "./use-user-gateway-model-permissions";
import { useUserGatewayEndpointPatternPermissions } from "./use-user-gateway-endpoint-pattern-permissions";
import { useUserGatewaySecretPatternPermissions } from "./use-user-gateway-secret-pattern-permissions";
import { useUserGatewayModelPatternPermissions } from "./use-user-gateway-model-pattern-permissions";

// Group-scoped hooks (param: groupName)
import { useGroupGatewayEndpointPermissions } from "./use-group-gateway-endpoint-permissions";
import { useGroupGatewaySecretPermissions } from "./use-group-gateway-secret-permissions";
import { useGroupGatewayModelPermissions } from "./use-group-gateway-model-permissions";
import { useGroupGatewayEndpointPatternPermissions } from "./use-group-gateway-endpoint-pattern-permissions";
import { useGroupGatewaySecretPatternPermissions } from "./use-group-gateway-secret-pattern-permissions";
import { useGroupGatewayModelPatternPermissions } from "./use-group-gateway-model-pattern-permissions";

// Import fetchers to mock
import * as gatewayService from "../services/gateway-service";

import type { UseAuthResult } from "./use-auth";

vi.mock("./use-auth");
vi.mock("../services/gateway-service");

const mockPermissions = [
  { name: "user1", permission: "MANAGE", kind: "user" },
];

describe("Gateway Permission Hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(useAuthModule, "useAuth").mockReturnValue({
      isAuthenticated: true,
    } as UseAuthResult);
  });

  const testHook = <
    P extends Record<string, unknown>,
    R extends Record<string, unknown>,
  >(
    hook: (props: P) => R,
    props: P,
    fetcherName: keyof typeof gatewayService,
  ) => {
    if (!hook) {
      console.error(`Hook for fetcher ${fetcherName} is undefined!`);
      return;
    }

    describe(hook.name || (fetcherName as string), () => {
      it(`fetches data for ${fetcherName as string} when props provided`, async () => {
        const spy = vi
          .spyOn(gatewayService, fetcherName)
          .mockResolvedValue(mockPermissions as never);
        const { result } = renderHook(() => hook(props));

        await waitFor(() => {
          const key = Object.keys(result.current).find(
            (k) => k === "permissions" || k.endsWith("Permissions"),
          );
          if (key) {
            expect(result.current[key]).toEqual(mockPermissions);
          }
        });
        expect(spy).toHaveBeenCalled();
      });

      it(`does not fetch for ${fetcherName as string} when props are null`, async () => {
        const spy = vi.spyOn(gatewayService, fetcherName);
        const nullProps = Object.keys(props).reduce(
          (acc, key) => ({ ...acc, [key]: null }),
          {} as P,
        );
        renderHook(() => hook(nullProps));

        await new Promise((resolve) => setTimeout(resolve, 10));
        expect(spy).not.toHaveBeenCalled();
      });
    });
  };

  // Resource-scoped: user permissions (param: name)
  testHook(
    useGatewayEndpointUserPermissions,
    { name: "endpoint-1" },
    "fetchGatewayEndpointUserPermissions",
  );
  testHook(
    useGatewayEndpointGroupPermissions,
    { name: "endpoint-1" },
    "fetchGatewayEndpointGroupPermissions",
  );
  testHook(
    useGatewaySecretUserPermissions,
    { name: "secret-1" },
    "fetchGatewaySecretUserPermissions",
  );
  testHook(
    useGatewaySecretGroupPermissions,
    { name: "secret-1" },
    "fetchGatewaySecretGroupPermissions",
  );
  testHook(
    useGatewayModelUserPermissions,
    { name: "model-1" },
    "fetchGatewayModelUserPermissions",
  );
  testHook(
    useGatewayModelGroupPermissions,
    { name: "model-1" },
    "fetchGatewayModelGroupPermissions",
  );

  // User-scoped: permissions (param: username)
  testHook(
    useUserGatewayEndpointPermissions,
    { username: "user1" },
    "fetchUserGatewayEndpointPermissions",
  );
  testHook(
    useUserGatewaySecretPermissions,
    { username: "user1" },
    "fetchUserGatewaySecretPermissions",
  );
  testHook(
    useUserGatewayModelPermissions,
    { username: "user1" },
    "fetchUserGatewayModelPermissions",
  );

  // User-scoped: pattern permissions (param: username)
  testHook(
    useUserGatewayEndpointPatternPermissions,
    { username: "user1" },
    "fetchUserGatewayEndpointPatternPermissions",
  );
  testHook(
    useUserGatewaySecretPatternPermissions,
    { username: "user1" },
    "fetchUserGatewaySecretPatternPermissions",
  );
  testHook(
    useUserGatewayModelPatternPermissions,
    { username: "user1" },
    "fetchUserGatewayModelPatternPermissions",
  );

  // Group-scoped: permissions (param: groupName)
  testHook(
    useGroupGatewayEndpointPermissions,
    { groupName: "group1" },
    "fetchGroupGatewayEndpointPermissions",
  );
  testHook(
    useGroupGatewaySecretPermissions,
    { groupName: "group1" },
    "fetchGroupGatewaySecretPermissions",
  );
  testHook(
    useGroupGatewayModelPermissions,
    { groupName: "group1" },
    "fetchGroupGatewayModelPermissions",
  );

  // Group-scoped: pattern permissions (param: groupName)
  testHook(
    useGroupGatewayEndpointPatternPermissions,
    { groupName: "group1" },
    "fetchGroupGatewayEndpointPatternPermissions",
  );
  testHook(
    useGroupGatewaySecretPatternPermissions,
    { groupName: "group1" },
    "fetchGroupGatewaySecretPatternPermissions",
  );
  testHook(
    useGroupGatewayModelPatternPermissions,
    { groupName: "group1" },
    "fetchGroupGatewayModelPatternPermissions",
  );
});
