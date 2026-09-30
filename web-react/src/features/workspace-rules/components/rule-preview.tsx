import type {
  WorkspaceRuleChange,
  WorkspaceRuleChangeAction,
} from "../../../shared/types/entity";

const ACTION_LABELS: Record<WorkspaceRuleChangeAction, string> = {
  grant: "Grant",
  update: "Update",
  keep: "Unchanged",
  remove: "Remove",
  skip: "Skip",
  shadowed: "Shadowed",
};

const ACTION_CLASSES: Record<WorkspaceRuleChangeAction, string> = {
  grant: "text-green-700 dark:text-green-300",
  update: "text-blue-700 dark:text-blue-300",
  keep: "text-ui-text-muted dark:text-ui-text-muted-dark",
  remove: "text-red-700 dark:text-red-300",
  skip: "text-amber-700 dark:text-amber-300",
  shadowed: "text-amber-700 dark:text-amber-300",
};

interface RulePreviewProps {
  changes: WorkspaceRuleChange[];
  /** Shown above the table, e.g. "Preview — nothing has been written". */
  caption?: string;
}

/**
 * The lines of a rule's plan: each matching group, its workspace, and what happens there.
 * Group and workspace names come from the directory and are rendered as text only.
 */
export function RulePreview({ changes, caption }: RulePreviewProps) {
  if (changes.length === 0) {
    return (
      <p
        className="text-sm text-ui-text-muted dark:text-ui-text-muted-dark"
        data-testid="rule-preview-empty"
      >
        No existing group matches this pattern.
      </p>
    );
  }

  return (
    <div>
      {caption && (
        <p className="mb-1 text-xs text-ui-text-muted dark:text-ui-text-muted-dark">
          {caption}
        </p>
      )}
      <div className="max-h-56 overflow-y-auto border border-ui-border dark:border-ui-border-dark rounded-md">
        <table
          className="w-full text-sm text-ui-text dark:text-ui-text-dark"
          aria-label="Rule preview"
        >
          <thead className="sticky top-0 bg-ui-bg dark:bg-ui-secondary-bg-dark">
            <tr className="text-left text-xs uppercase opacity-70">
              <th className="px-2 py-1 font-semibold">Group</th>
              <th className="px-2 py-1 font-semibold">Workspace</th>
              <th className="px-2 py-1 font-semibold">Result</th>
              <th className="px-2 py-1 font-semibold">Permission</th>
              <th className="px-2 py-1 font-semibold">Reason</th>
            </tr>
          </thead>
          <tbody>
            {changes.map((change) => (
              <tr
                key={`${change.workspace}\u0000${change.group}\u0000${change.action}`}
                className="border-t border-ui-border dark:border-ui-border-dark"
              >
                <td className="px-2 py-1 font-mono break-all">
                  {change.group}
                </td>
                <td className="px-2 py-1 font-mono break-all">
                  {change.workspace}
                </td>
                <td
                  className={`px-2 py-1 font-medium ${ACTION_CLASSES[change.action]}`}
                >
                  {ACTION_LABELS[change.action]}
                </td>
                <td className="px-2 py-1">
                  {change.previous
                    ? `${change.previous} → ${change.permission ?? ""}`
                    : (change.permission ?? "-")}
                </td>
                <td className="px-2 py-1">{change.reason ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
