import type { GrantWorkspaceScope } from "../hooks/use-grant-workspace-scope";

/**
 * Says which workspace the grants on a page belong to. Renders nothing for a type whose grants
 * are not workspace-scoped, or with workspaces disabled.
 */
export function GrantWorkspaceNotice({
  scope,
}: {
  scope: GrantWorkspaceScope;
}) {
  if (!scope.scoped) return null;
  if (scope.workspace) {
    return (
      <p
        role="status"
        className="mb-3 text-sm text-ui-text-muted dark:text-ui-text-muted-dark"
      >
        Grants shown here belong to workspace{" "}
        <span className="font-semibold">{scope.workspace}</span>. Switch
        workspaces in the header to see or change another workspace&apos;s
        grants.
      </p>
    );
  }
  return (
    <p
      role="status"
      className="mb-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-900/30 dark:text-amber-200"
    >
      These are the <span className="font-semibold">default</span>{" "}
      workspace&apos;s grants. A grant on a model, prompt or AI Gateway resource
      belongs to one workspace: choose a workspace in the header to add, change
      or remove grants.
    </p>
  );
}

/** The tooltip for a grant control that is disabled while "All Workspaces" is selected. */
export const CHOOSE_WORKSPACE_TITLE =
  "Choose a workspace in the header to change grants";
