import { SearchInput } from "../../shared/components/search-input";
import { useAllExperiments } from "../../core/hooks/use-all-experiments";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { ExperimentListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import { useSearch } from "../../core/hooks/use-search";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";

const experimentColumns: ColumnConfig<ExperimentListItem>[] = [
  {
    header: "ID",
    render: (item) => item.id,
  },
  {
    header: "Experiment Name",
    render: (item) => item.name,
  },
  {
    header: "Tags",
    render: (item) =>
      Object.entries(item.tags)
        .map(([key, value]) => `${key}: ${value}`)
        .join(", "),
  },
];

export default function ExperimentsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allExperiments } = useAllExperiments();

  const experimentsList = allExperiments || [];

  const filteredExperiments = experimentsList.filter((experiment) =>
    experiment.name.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  return (
    <PageContainer title="Experiments Page">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading experiments list..."
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
            placeholder="Search experiments..."
          />

          <ResultsHeader count={filteredExperiments.length} />

          <EntityListTable
            mode="object"
            data={filteredExperiments}
            columns={experimentColumns}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
