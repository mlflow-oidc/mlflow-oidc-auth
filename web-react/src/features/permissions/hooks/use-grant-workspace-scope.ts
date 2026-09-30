import { use } from "react";
import { RuntimeConfigContext } from "../../../shared/context/use-runtime-config";
import { useSelectedWorkspace } from "../../../shared/context/use-workspace";
import type { PermissionType } from "../../../shared/types/entity";

/**
 * Resource types whose grants belong to one workspace. MLflow keeps registered models, prompts
 * and AI Gateway resources unique per workspace and name, so the server records each grant on
 * them in the workspace the request names — the one selected in the workspace picker, or
 * `default` with "All Workspaces". Experiment grants are keyed by id and are not listed.
 */
export const WORKSPACE_SCOPED_PERMISSION_TYPES: ReadonlySet<PermissionType> =
  new Set<PermissionType>([
    "models",
    "prompts",
    "ai-endpoints",
    "ai-secrets",
    "ai-models",
  ]);

export type GrantWorkspaceScope = {
  /** Whether grants of this type belong to one workspace in this deployment. */
  scoped: boolean;
  /** The workspace selected in the picker; null for "All Workspaces". */
  workspace: string | null;
  /**
   * Whether grants may be added, changed or removed here. False for a workspace-scoped type
   * while "All Workspaces" is selected, where a change would silently land in `default`.
   */
  canChange: boolean;
};

/**
 * Which workspace a page's grants belong to, and whether they may be changed there. The server
 * enforces the scoping either way; this only keeps the UI from implying a grant applies
 * everywhere. Outside a runtime config (tests), workspaces count as disabled.
 */
export function useGrantWorkspaceScope(
  type: PermissionType,
): GrantWorkspaceScope {
  const config = use(RuntimeConfigContext);
  const workspace = useSelectedWorkspace();
  const scoped =
    Boolean(config?.workspaces_enabled) &&
    WORKSPACE_SCOPED_PERMISSION_TYPES.has(type);
  return { scoped, workspace, canChange: !scoped || workspace !== null };
}

/** The tooltip for a grant control that is disabled while "All Workspaces" is selected. */
export const CHOOSE_WORKSPACE_TITLE =
  "Choose a workspace in the header to change grants";

/** A grant control's tooltip: `title`, or why the control is disabled when grants cannot change. */
export function grantControlTitle(
  scope: GrantWorkspaceScope,
  title: string | undefined,
): string | undefined {
  return scope.canChange ? title : CHOOSE_WORKSPACE_TITLE;
}
