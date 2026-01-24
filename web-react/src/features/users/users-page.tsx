import { SearchInput } from "../../shared/components/search-input";
import { useAllUsers } from "../../core/hooks/use-all-users";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useSearch } from "../../core/hooks/use-search";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
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
    username.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const tableData = filteredUsers.map((username) => ({
    id: username,
    username,
  }));

  const renderPermissionsButton = (username: string) => (
    <div className="invisible group-hover:visible">
      <RowActionButton
        entityId={`${username}/experiments`}
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
    <PageContainer title="Users">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading users list..."
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
              placeholder="Search users..."
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
