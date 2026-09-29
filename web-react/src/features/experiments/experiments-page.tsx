import { usePagedList } from "../../core/hooks/use-paged-list";
import { fetchExperimentsPage } from "../../core/services/entity-service";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { ExperimentListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityNameLink } from "../../shared/components/entity-name-link";
import { buildEntityRoute } from "../../shared/utils/string-utils";

export default function ExperimentsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, items, pagination } = usePagedList(
    fetchExperimentsPage,
    submittedTerm,
  );

  const getRowHref = (experiment: ExperimentListItem) =>
    buildEntityRoute("/experiments", experiment.id);

  const columns: ColumnConfig<ExperimentListItem>[] = [
    {
      header: "Experiment Name",
      render: (item) => (
        <EntityNameLink to={getRowHref(item)} title={item.name}>
          {item.name}
        </EntityNameLink>
      ),
    },
  ];

  return (
    <PageContainer title="Experiments">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading experiments list..."
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
              placeholder="Search experiments..."
            />
          </div>

          <EntityListTable
            getRowHref={getRowHref}
            data={items}
            pagination={pagination}
            columns={columns}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
