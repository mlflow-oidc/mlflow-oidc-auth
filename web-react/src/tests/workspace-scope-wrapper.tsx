import type React from "react";
import { vi } from "vitest";
import { RuntimeConfigContext } from "../shared/context/use-runtime-config";
import { WorkspaceContext } from "../shared/context/use-workspace";
import type { RuntimeConfig } from "../shared/services/runtime-config";

const CONFIG: RuntimeConfig = {
  basePath: "",
  uiPath: "/oidc/ui",
  provider: "oidc",
  authenticated: true,
  gen_ai_gateway_enabled: true,
  workspaces_enabled: true,
};

/**
 * A render wrapper with a runtime config and a workspace picker selection, for tests of grant
 * workspace scoping. `selected` null is "All Workspaces".
 */
export function workspaceScopeWrapper(
  workspacesEnabled: boolean,
  selected: string | null,
) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <RuntimeConfigContext
        value={{ ...CONFIG, workspaces_enabled: workspacesEnabled }}
      >
        <WorkspaceContext
          value={{ selectedWorkspace: selected, setSelectedWorkspace: vi.fn() }}
        >
          {children}
        </WorkspaceContext>
      </RuntimeConfigContext>
    );
  };
}
