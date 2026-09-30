import type { WorkspaceRuleMode } from "../../../shared/types/entity";

const BADGE_BASE_CLASSES =
  "inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-medium border whitespace-nowrap";

const MODE_CLASSES: Record<WorkspaceRuleMode, string> = {
  report:
    "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800",
  enforce:
    "bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800",
};

const MODE_LABELS: Record<WorkspaceRuleMode, string> = {
  report: "Report",
  enforce: "Enforce",
};

const MODE_TITLES: Record<WorkspaceRuleMode, string> = {
  report: "Report only: says what it would grant, writes nothing",
  enforce: "Enforced: grants workspace permissions to matching groups",
};

/** A rule's mode: `report` writes nothing, `enforce` grants. */
export function RuleModeBadge({ mode }: { mode: WorkspaceRuleMode }) {
  return (
    <span
      className={`${BADGE_BASE_CLASSES} ${MODE_CLASSES[mode]}`}
      title={MODE_TITLES[mode]}
    >
      {MODE_LABELS[mode]}
    </span>
  );
}
