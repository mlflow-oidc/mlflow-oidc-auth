import { useState } from "react";
import { Navigate } from "react-router";
import { faEdit, faTrash, faPlus } from "@fortawesome/free-solid-svg-icons";
import { useAllWorkspaces } from "../../core/hooks/use-all-workspaces";
import { useSearch } from "../../core/hooks/use-search";
import { useUser } from "../../core/hooks/use-user";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import { useToast } from "../../shared/components/toast/use-toast";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { Button } from "../../shared/components/button";
import { IconButton } from "../../shared/components/icon-button";
import type { WorkspaceListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { RowActionButton } from "../../shared/components/row-action-button";
import { deleteWorkspace } from "../../core/services/workspace-service";
import { CreateWorkspaceModal } from "./components/create-workspace-modal";
import { EditWorkspaceModal } from "./components/edit-workspace-modal";
import { DeleteWorkspaceModal } from "./components/delete-workspace-modal";

export default function WorkspacesPage() {
  const { workspaces_enabled } = useRuntimeConfig();
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();
  const { allWorkspaces, memberCounts, isLoading, error, refresh } = useAllWorkspaces();
  const { currentUser } = useUser();
  const { showToast } = useToast();

  const isAdmin = currentUser?.is_admin ?? false;

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editWorkspace, setEditWorkspace] = useState<{
    name: string;
    description: string;
    default_artifact_root?: string | null;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{
    name: string;
    description: string;
  } | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  if (!workspaces_enabled) return <Navigate to="/" replace />;

  const workspacesList = allWorkspaces || [];

  const filteredWorkspaces = workspacesList.filter((ws) =>
    ws.name.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await deleteWorkspace(deleteTarget.name);
      showToast(`Workspace '${deleteTarget.name}' deleted`, "success");
      setDeleteTarget(null);
      refresh();
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to delete workspace";
      showToast(msg, "error");
    } finally {
      setIsDeleting(false);
    }
  };

  const columns: ColumnConfig<WorkspaceListItem>[] = [
    {
      header: "Workspace Name",
      render: (item) => item.name,
    },
    {
      header: "Description",
      render: (item) => item.description || "—",
    },
    {
      header: "Artifact Root",
      render: (item) => item.default_artifact_root || "—",
    },
    {
      header: "Members",
      render: (item) => (
        <span className="text-sm text-ui-text dark:text-ui-text-dark">
          {memberCounts?.[item.name]?.users ?? "…"} users,{" "}
          {memberCounts?.[item.name]?.groups ?? "…"} groups
        </span>
      ),
    },
    {
      header: "Actions",
      render: (workspace) => (
        <div className="invisible group-hover:visible flex space-x-1">
          <RowActionButton
            entityId={workspace.name}
            route="/workspaces"
            buttonText="Manage members"
          />
          {isAdmin && (
            <>
              <IconButton
                icon={faEdit}
                title="Edit workspace"
                onClick={() =>
                  setEditWorkspace({
                    name: workspace.name,
                    description: workspace.description,
                    default_artifact_root: workspace.default_artifact_root,
                  })
                }
              />
              <IconButton
                icon={faTrash}
                title="Delete workspace"
                onClick={() =>
                  setDeleteTarget({
                    name: workspace.name,
                    description: workspace.description,
                  })
                }
              />
            </>
          )}
        </div>
      ),
      className: "flex-shrink-0",
    },
  ];

  return (
    <PageContainer title="Workspaces">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading workspaces..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mb-2 flex items-center gap-6">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search workspaces..."
            />
            {isAdmin && (
              <Button
                variant="secondary"
                onClick={() => setIsCreateOpen(true)}
                icon={faPlus}
                className="whitespace-nowrap h-8 mb-1 mt-2"
              >
                Create Workspace
              </Button>
            )}
          </div>

          <EntityListTable
            data={filteredWorkspaces}
            columns={columns}
            searchTerm={submittedTerm}
          />

          <CreateWorkspaceModal
            isOpen={isCreateOpen}
            onClose={() => setIsCreateOpen(false)}
            onSuccess={refresh}
          />
          <EditWorkspaceModal
            isOpen={!!editWorkspace}
            onClose={() => setEditWorkspace(null)}
            onSuccess={refresh}
            workspace={editWorkspace}
          />
          <DeleteWorkspaceModal
            isOpen={!!deleteTarget}
            onClose={() => setDeleteTarget(null)}
            onConfirm={() => void handleDelete()}
            workspace={deleteTarget}
            isProcessing={isDeleting}
          />
        </>
      )}
    </PageContainer>
  );
}
