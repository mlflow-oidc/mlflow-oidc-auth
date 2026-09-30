import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import type { PermissionType } from "../../../shared/types/entity";
import { workspaceScopeWrapper } from "../../../tests/workspace-scope-wrapper";
import {
  CHOOSE_WORKSPACE_TITLE,
  grantControlTitle,
  useGrantWorkspaceScope,
} from "./use-grant-workspace-scope";

describe("useGrantWorkspaceScope", () => {
  it.each<PermissionType>([
    "models",
    "prompts",
    "ai-endpoints",
    "ai-secrets",
    "ai-models",
  ])("%s grants belong to the selected workspace", (type) => {
    const { result } = renderHook(() => useGrantWorkspaceScope(type), {
      wrapper: workspaceScopeWrapper(true, "team-a"),
    });
    expect(result.current).toEqual({
      scoped: true,
      workspace: "team-a",
      canChange: true,
    });
  });

  it("blocks changes to workspace-scoped grants while All Workspaces is selected", () => {
    const { result } = renderHook(() => useGrantWorkspaceScope("models"), {
      wrapper: workspaceScopeWrapper(true, null),
    });
    expect(result.current.canChange).toBe(false);
  });

  it("does not scope experiment grants, which are keyed by id", () => {
    const { result } = renderHook(() => useGrantWorkspaceScope("experiments"), {
      wrapper: workspaceScopeWrapper(true, null),
    });
    expect(result.current).toEqual({
      scoped: false,
      workspace: null,
      canChange: true,
    });
  });

  it("does not scope anything with workspaces disabled, or outside a runtime config", () => {
    expect(
      renderHook(() => useGrantWorkspaceScope("models"), {
        wrapper: workspaceScopeWrapper(false, null),
      }).result.current.canChange,
    ).toBe(true);
    expect(
      renderHook(() => useGrantWorkspaceScope("models")).result.current.scoped,
    ).toBe(false);
  });
});

const SCOPED_IN_TEAM_A = { scoped: true, workspace: "team-a", canChange: true };
const SCOPED_ALL = { scoped: true, workspace: null, canChange: false };

describe("grantControlTitle", () => {
  it("keeps the control's own title while grants may change", () => {
    expect(grantControlTitle(SCOPED_IN_TEAM_A, "Edit permission")).toBe(
      "Edit permission",
    );
    expect(grantControlTitle(SCOPED_IN_TEAM_A, undefined)).toBeUndefined();
  });

  it("explains a disabled control under All Workspaces", () => {
    expect(grantControlTitle(SCOPED_ALL, "Edit permission")).toBe(
      CHOOSE_WORKSPACE_TITLE,
    );
  });
});
