import React, { useState } from "react";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { useAllGroups } from "../../../core/hooks/use-all-groups";
import { useApi } from "../../../core/hooks/use-api";
import { fetchAllWorkspaces } from "../../../core/services/workspace-service";
import type { WorkspaceListResponse } from "../../../shared/types/entity";
import { buildRulePattern } from "../rule-builder";
import { SearchableSelect } from "./searchable-select";

// Rules never grant the shared default workspace (the server skips it), so it is not offered.
const DEFAULT_WORKSPACE = "default";

interface RuleBuilderModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Called with the built pattern and a suggested rule name. */
  onApply: (pattern: string, suggestedName: string) => void;
}

/**
 * Build a rule pattern by example: pick an existing group and the workspace it should get. Opened
 * from the rule dialog; the pattern it builds goes back into that dialog, where it can still be
 * edited and previewed before anything is saved.
 */
export const RuleBuilderModal: React.FC<RuleBuilderModalProps> = ({
  isOpen,
  onClose,
  onApply,
}) => (
  <Modal isOpen={isOpen} onClose={onClose} title="Rule builder">
    {isOpen && <RuleBuilderForm onClose={onClose} onApply={onApply} />}
  </Modal>
);

const RuleBuilderForm: React.FC<Omit<RuleBuilderModalProps, "isOpen">> = ({
  onClose,
  onApply,
}) => {
  const { allGroups, isLoading: groupsLoading } = useAllGroups();
  const { data: workspaceData, isLoading: workspacesLoading } =
    useApi<WorkspaceListResponse>(fetchAllWorkspaces);
  const [group, setGroup] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [everyLikeGroup, setEveryLikeGroup] = useState(false);

  const workspaces = (workspaceData?.workspaces ?? [])
    .map((w) => w.name)
    .filter((name) => name !== DEFAULT_WORKSPACE)
    .sort();
  const groups = [...(allGroups ?? [])].sort();
  const built =
    group && workspace
      ? buildRulePattern(group, workspace, everyLikeGroup)
      : null;

  return (
    <div className="text-ui-text dark:text-ui-text-dark">
      <p className="mb-4 text-sm">
        Pick an existing group and the workspace it should get. The group&apos;s
        name must contain the workspace&apos;s name, e.g.{" "}
        <code>team-acme-ds</code> and <code>acme</code>.
      </p>

      <SearchableSelect
        id="rule-builder-group"
        label="Group"
        options={groups}
        value={group}
        onChange={setGroup}
        placeholder="Search groups..."
        isLoading={groupsLoading}
        emptyText="No group matches"
      />
      <SearchableSelect
        id="rule-builder-workspace"
        label="Workspace"
        options={workspaces}
        value={workspace}
        onChange={setWorkspace}
        placeholder="Search workspaces..."
        isLoading={workspacesLoading}
        emptyText="No workspace matches"
      />
      <p className="-mt-2 mb-3 text-xs text-ui-text-muted dark:text-ui-text-muted-dark">
        The default workspace is not listed: rules never grant it.
      </p>

      <label className="flex items-start gap-2 mb-4 text-sm cursor-pointer">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={everyLikeGroup}
          onChange={(e) => setEveryLikeGroup(e.target.checked)}
        />
        <span>
          Match every group with the same shape
          <span className="block text-xs text-ui-text-muted dark:text-ui-text-muted-dark">
            Also covers future groups such as other tenants&apos; — each gets
            the workspace named in its own group name.
          </span>
        </span>
      </label>

      {built?.ok && (
        <div className="mb-4 text-sm">
          <div className="font-semibold opacity-70 mb-1">Pattern</div>
          <code
            className="block p-2 rounded border border-ui-border dark:border-ui-border-dark break-all"
            data-testid="rule-builder-pattern"
          >
            {built.pattern}
          </code>
        </div>
      )}
      {built && !built.ok && (
        <p role="alert" className="mb-4 text-sm text-red-500">
          {built.reason}
        </p>
      )}

      <div className="flex justify-end space-x-3">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={!built?.ok}
          onClick={() => {
            if (built?.ok) onApply(built.pattern, built.name);
          }}
        >
          Use pattern
        </Button>
      </div>
    </div>
  );
};
