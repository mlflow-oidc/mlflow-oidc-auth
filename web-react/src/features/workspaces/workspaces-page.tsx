import { useAllWorkspaces } from "../../core/hooks/use-all-workspaces";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { WorkspaceListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { RowActionButton } from "../../shared/components/row-action-button";

export default function WorkspacesPage() {
  const { searchTerm, submittedTerm, handleInputChange, handleSearchSubmit, handleClearSearch } = useSearch();
  const { allWorkspaces, isLoading, error, refresh } = useAllWorkspaces();

  const workspacesList = allWorkspaces || [];

  const filteredWorkspaces = workspacesList.filter((ws) => ws.name.toLowerCase().includes(submittedTerm.toLowerCase()));

  const renderManageButton = (workspace: WorkspaceListItem) => (
    <div className="invisible group-hover:visible">
      <RowActionButton entityId={workspace.name} route="/workspaces" buttonText="Manage members" />
    </div>
  );

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
      header: "Members",
      render: (item) => renderManageButton(item),
      className: "flex-shrink-0",
    },
  ];

  return (
    <PageContainer title="Workspaces">
      <PageStatus isLoading={isLoading} loadingText="Loading workspaces..." error={error} onRetry={refresh} />

      {!isLoading && !error && (
        <>
          <div className="mb-2">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search workspaces..."
            />
          </div>

          <EntityListTable data={filteredWorkspaces} columns={columns} searchTerm={submittedTerm} />
        </>
      )}
    </PageContainer>
  );
}
