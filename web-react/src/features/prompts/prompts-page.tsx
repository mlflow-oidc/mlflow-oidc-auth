import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { PromptListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import { useSearch } from "../../core/hooks/use-search";
import { useAllPrompts } from "../../core/hooks/use-all-prompts";

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

  const filteredPrompts = promptsList.filter((prompt) =>
    prompt.name.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  if (isLoading) {
    return (
      <div className="flex h-full justify-center items-center p-8">
        <p className="text-lg font-medium animate-pulse text-text-primary dark:text-text-primary-dark">
          Loading models list...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-wrap h-full justify-center content-center items-center gap-2 text-red-600">
        <p className="text-xl">Error fetching models: {error.message}</p>
        <button
          type="button"
          onClick={() => refresh()}
          className="ml-4 p-2 bg-red-100 rounded hover:bg-red-200 cursor-pointer"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <>
      <h2 className="flex-shrink-0 text-3xl font-semibold mb-6 text-center">
        Models Page
      </h2>

      <SearchInput
        value={searchTerm}
        onInputChange={handleInputChange}
        onSubmit={handleSearchSubmit}
        onClear={handleClearSearch}
        placeholder="Search models..."
      />

      <h3 className="text-base font-medium p-1 mb-1">
        Results ({filteredPrompts.length})
      </h3>

      <EntityListTable
        mode="object"
        data={filteredPrompts}
        columns={promptsColumns}
        searchTerm={submittedTerm}
      />
    </>
  );
}
