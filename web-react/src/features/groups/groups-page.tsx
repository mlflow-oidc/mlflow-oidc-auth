import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { useSearch } from "../../core/hooks/use-search";
import { useAllGroups } from "../../core/hooks/use-all-groups";
import { RowActionButton } from "../../shared/components/row-action-button";
import type { ColumnConfig } from "../../shared/types/table";

export default function GroupsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allGroups } = useAllGroups();

  const groupsList = allGroups || [];

  const filteredGroups = groupsList.filter((group) =>
    group.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const tableData = filteredGroups.map((group) => ({
    id: group,
    groupName: group,
  }));

  const renderPermissionsButton = (groupName: string) => (
    <div className="invisible group-hover:visible">
      <RowActionButton
        entityId={`${groupName}/experiments`}
        route="/groups"
        buttonText="Manage permissions"
      />
    </div>
  );

  const columnsWithAction: ColumnConfig<{ id: string; groupName: string }>[] = [
    {
      header: "Group Name",
      render: ({ groupName }) => groupName,
    },
    {
      header: "Permissions",
      render: ({ groupName }) => renderPermissionsButton(groupName),
      className: "flex-shrink-0",
    },
  ];

  return (
    <PageContainer title="Groups">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading groups list..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mb-2">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search groups..."
             />
          </div>

          <EntityListTable
            mode="object"
            data={tableData}
            searchTerm={submittedTerm}
            columns={columnsWithAction}
          />
        </>
      )}
    </PageContainer>
  );
}


