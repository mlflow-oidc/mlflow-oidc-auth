import { SearchInput } from "../../shared/components/search-input";
import { useAllUsers } from "../../core/hooks/use-all-users";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useSearch } from "../../core/hooks/use-search";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";
import { RowActionButton } from "../../shared/components/row-action-button";
import type { ColumnConfig } from "../../shared/types/table";

export default function UsersPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allUsers } = useAllUsers();

  const usersList = allUsers || [];

  const filteredUsers = usersList.filter((username) =>
    username.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const tableData = filteredUsers.map((username) => ({
    id: username,
    username,
  }));

  const renderPermissionsButton = (item: string) => (
    <div className="invisible group-hover:visible">
      <RowActionButton
        entityId={item}
        route="/users"
        buttonText="Manage permissions"
      />
    </div>
  );

  const columnsWithAction: ColumnConfig<{ id: string; username: string }>[] = [
    {
      header: "Username",
      render: ({ username }) => username,
    },
    {
      header: "Permissions",
      render: ({ username }) => renderPermissionsButton(username),
      className: "flex-shrink-0",
    },
  ];

  return (
    <PageContainer title="Users Page">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading users list..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <SearchInput
            value={searchTerm}
            onInputChange={handleInputChange}
            onSubmit={handleSearchSubmit}
            onClear={handleClearSearch}
            placeholder="Search users..."
          />
          <ResultsHeader count={filteredUsers.length} />
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
