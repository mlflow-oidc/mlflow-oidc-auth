import { useCallback, useState } from "react";
import { Navigate } from "react-router";
import { faEdit, faTrash, faPlus } from "@fortawesome/free-solid-svg-icons";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { Button } from "../../shared/components/button";
import { IconButton } from "../../shared/components/icon-button";
import { useToast } from "../../shared/components/toast/use-toast";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import { useUser } from "../../core/hooks/use-user";
import { useWorkspaceRules } from "../../core/hooks/use-workspace-rules";
import { deleteWorkspaceRule } from "../../core/services/workspace-rule-service";
import { extractErrorMessage } from "../../core/services/http";
import { formatDateTime } from "../../shared/utils/format-date-time";
import type { WorkspaceRule } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import { RuleModeBadge } from "./components/rule-mode-badge";
import { WorkspaceRuleModal } from "./components/workspace-rule-modal";
import { DeleteWorkspaceRuleModal } from "./components/delete-workspace-rule-modal";

/**
 * Admin page for workspace group rules (issue #419): rules that attach groups to workspaces by
 * group name. Hidden unless workspaces are enabled. The server is the authority on both — every
 * endpoint is admin-only and answers 404 with workspaces off — so this gating is cosmetic.
 */
export default function WorkspaceRulesPage() {
  const { workspaces_enabled } = useRuntimeConfig();
  const { currentUser } = useUser();
  const isAdmin = currentUser?.is_admin ?? false;

  if (!workspaces_enabled) return <Navigate to="/" replace />;
  if (currentUser && !isAdmin) return <Navigate to="/403" replace />;

  return <WorkspaceRulesList />;
}

function WorkspaceRulesList() {
  const {
    rules,
    allowedPermissions,
    maxPermission,
    isLoading,
    error,
    refresh,
  } = useWorkspaceRules();
  const { showToast } = useToast();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<WorkspaceRule | null>(null);
  const [deletingRule, setDeletingRule] = useState<WorkspaceRule | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleConfirmDelete = useCallback(async () => {
    if (!deletingRule) return;
    setIsDeleting(true);
    try {
      const plan = await deleteWorkspaceRule(deletingRule.id);
      // A delete also lists grants a rule it shadowed took over; count only this rule's removals.
      const removed = plan.changes.filter(
        (c) =>
          c.applied && c.action === "remove" && c.rule_id === deletingRule.id,
      ).length;
      showToast(
        `Rule "${deletingRule.name}" deleted; ${removed} workspace permission(s) removed`,
        "success",
      );
      setDeletingRule(null);
      refresh();
    } catch (err) {
      showToast(
        extractErrorMessage(
          err,
          `Failed to delete rule "${deletingRule.name}"`,
        ),
        "error",
      );
    } finally {
      setIsDeleting(false);
    }
  }, [deletingRule, refresh, showToast]);

  const columns: ColumnConfig<WorkspaceRule>[] = [
    {
      header: "Name",
      render: (rule) => (
        <span className="truncate block" title={rule.name}>
          {rule.name}
        </span>
      ),
    },
    {
      header: "Pattern",
      render: (rule) => (
        <code className="truncate block max-w-xs" title={rule.pattern}>
          {rule.pattern}
        </code>
      ),
    },
    {
      header: "Permission",
      render: (rule) => rule.permission,
    },
    {
      header: "Mode",
      render: (rule) => <RuleModeBadge mode={rule.mode} />,
    },
    {
      header: "Enabled",
      render: (rule) => (rule.enabled ? "Yes" : "No"),
    },
    {
      header: "Last change",
      render: (rule) => (
        <span title={rule.created_by ? `Created by ${rule.created_by}` : ""}>
          {formatDateTime(rule.updated_at)}
        </span>
      ),
    },
    {
      header: "Actions",
      render: (rule) => (
        <div className="flex space-x-1">
          <IconButton
            icon={faEdit}
            title={`Edit rule ${rule.name}`}
            muted
            onClick={() => setEditingRule(rule)}
          />
          <IconButton
            icon={faTrash}
            title={`Delete rule ${rule.name}`}
            muted
            onClick={() => setDeletingRule(rule)}
          />
        </div>
      ),
      className: "flex-shrink-0",
    },
  ];

  return (
    <PageContainer title="Workspace rules">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading workspace rules..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mb-2 flex items-center justify-between gap-6">
            <p className="text-sm text-ui-text-muted dark:text-ui-text-muted-dark">
              Rules attach groups to workspaces by group name. When several
              rules match the same group and workspace, the oldest rule wins.
            </p>
            <Button
              variant="secondary"
              onClick={() => setIsCreateOpen(true)}
              icon={faPlus}
              className="whitespace-nowrap h-8 mb-1 mt-2"
            >
              Create Rule
            </Button>
          </div>

          <EntityListTable data={rules} columns={columns} searchTerm="" />

          <WorkspaceRuleModal
            isOpen={isCreateOpen}
            onClose={() => setIsCreateOpen(false)}
            onSuccess={refresh}
            rule={null}
            allowedPermissions={allowedPermissions}
            maxPermission={maxPermission}
          />
          <WorkspaceRuleModal
            isOpen={!!editingRule}
            onClose={() => setEditingRule(null)}
            onSuccess={refresh}
            rule={editingRule}
            allowedPermissions={allowedPermissions}
            maxPermission={maxPermission}
          />
          <DeleteWorkspaceRuleModal
            isOpen={!!deletingRule}
            onClose={() => setDeletingRule(null)}
            onConfirm={() => void handleConfirmDelete()}
            rule={deletingRule}
            isProcessing={isDeleting}
          />
        </>
      )}
    </PageContainer>
  );
}
