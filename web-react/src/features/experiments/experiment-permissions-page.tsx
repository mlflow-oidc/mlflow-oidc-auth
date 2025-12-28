import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import type { ColumnConfig } from "../../shared/types/table";
import type { EntityPermission } from "../../shared/types/entity";
import { useSearch } from "../../core/hooks/use-search";
import { useExperimentUserPermissions } from "../../core/hooks/use-experiment-user-permissions";
import { useAllExperiments } from "../../core/hooks/use-all-experiments";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";
import { SearchInput } from "../../shared/components/search-input";

const experimentPermissionsColumns: ColumnConfig<EntityPermission>[] = [
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

export default function ExperimentPermissionsPage() {
  const { experimentId: routeExperimentId } = useParams<{
    experimentId: string;
  }>();

  const experimentId = routeExperimentId || null;

  const { isLoading, error, refresh, experimentUserPermissions } =
    useExperimentUserPermissions({ experimentId });

  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { allExperiments } = useAllExperiments();

  if (!experimentId) {
    return <div>Experiment ID is required.</div>;
  }

  const permissionsList = experimentUserPermissions || [];

  const filteredPermissions = permissionsList.filter((p) =>
    p.username.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const experiment = allExperiments?.find((e) => e.id === experimentId);
  const experimentName = experiment?.name || experimentId;

  return (
    <PageContainer title={`Permissions for Experiment ${experimentName}`}>
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
            columns={experimentPermissionsColumns}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
