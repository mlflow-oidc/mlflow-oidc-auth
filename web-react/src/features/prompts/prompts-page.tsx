import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { PromptListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import { useSearch } from "../../core/hooks/use-search";
import { useAllPrompts } from "../../core/hooks/use-all-prompts";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";

const promptsColumns: ColumnConfig<PromptListItem>[] = [
  {
    header: "Name",
    render: (item) => item.name,
  },
  {
    header: "Description",
    render: (item) => item.description,
  },
];

export default function PromptsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allPrompts } = useAllPrompts();

  const promptsList = allPrompts || [];

  const filteredPrompts = promptsList.filter((p) =>
    p.name.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  return (
    <PageContainer title="Prompts Page">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading prompts list..."
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
            placeholder="Search prompts..."
          />
          <ResultsHeader count={filteredPrompts.length} />
          <EntityListTable
            mode="object"
            data={filteredPrompts}
            columns={promptsColumns}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
