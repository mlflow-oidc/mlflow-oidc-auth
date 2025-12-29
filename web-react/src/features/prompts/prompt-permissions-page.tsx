import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import type { ColumnConfig } from "../../shared/types/table";
import type { EntityPermission } from "../../shared/types/entity";
import { useSearch } from "../../core/hooks/use-search";
import { usePromptUserPermissions } from "../../core/hooks/use-prompt-user-permissions";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";
import { SearchInput } from "../../shared/components/search-input";

const promptPermissionsColumns: ColumnConfig<EntityPermission>[] = [
  {
    header: "Name",
    render: (item) => item.username,
  },
  {
    header: "Permission",
    render: (item) => item.permission,
  },
  {
    header: "Kind",
    render: (item) => item.kind,
  },
];

export default function PromptPermissionsPage() {
  const { promptName } = useParams<{
    promptName: string;
  }>();

  const { isLoading, error, refresh, promptUserPermissions } =
    usePromptUserPermissions({ promptName: promptName || null });

  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  if (!promptName) {
    return <div>Prompt Name is required.</div>;
  }

  const permissionsList = promptUserPermissions || [];

  const filteredPermissions = permissionsList.filter((p) =>
    p.username.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  return (
    <PageContainer title={`Permissions for Prompt ${promptName}`}>
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading permissions list..."
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
            placeholder="Search permissions..."
          />
          <ResultsHeader count={filteredPermissions.length} />
          <EntityListTable
            mode="object"
            data={filteredPermissions}
            columns={promptPermissionsColumns}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
