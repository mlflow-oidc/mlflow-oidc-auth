import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import type { ColumnConfig } from "../../shared/types/table";
import type { EntityPermission } from "../../shared/types/entity";
import { useSearch } from "../../core/hooks/use-search";
import { useModelUserPermissions } from "../../core/hooks/use-model-user-permissions";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";
import { SearchInput } from "../../shared/components/search-input";

const modelPermissionsColumns: ColumnConfig<EntityPermission>[] = [
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

export default function ModelPermissionsPage() {
  const { modelName } = useParams<{
    modelName: string;
  }>();

  const { isLoading, error, refresh, modelUserPermissions } =
    useModelUserPermissions({ modelName: modelName || null });

  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  if (!modelName) {
    return <div>Model Name is required.</div>;
  }

  const permissionsList = modelUserPermissions || [];

  const filteredPermissions = permissionsList.filter((p) =>
    p.username.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  return (
    <PageContainer title={`Permissions for Model ${modelName}`}>
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
            columns={modelPermissionsColumns}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
