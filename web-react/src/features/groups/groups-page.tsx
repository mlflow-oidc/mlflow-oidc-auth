import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useSearch } from "../../core/hooks/use-search";
import { useAllGroups } from "../../core/hooks/use-all-groups";

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

  if (isLoading) {
    return (
      <div className="flex h-full justify-center items-center p-8">
        <p className="text-lg font-medium animate-pulse text-text-primary dark:text-text-primary-dark">
          Loading groups list...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-wrap h-full justify-center content-center items-center gap-2 text-red-600">
        <p className="text-xl">Error fetching groups: {error.message}</p>
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
        Groups Page
      </h2>

      <SearchInput
        value={searchTerm}
        onInputChange={handleInputChange}
        onSubmit={handleSearchSubmit}
        onClear={handleClearSearch}
        placeholder="Search groups..."
      />

      <h3 className="text-base font-medium p-1 mb-1">
        Results ({filteredGroups.length})
      </h3>

      <EntityListTable
        mode="primitive"
        data={filteredGroups}
        searchTerm={searchTerm}
      />
    </>
  );
}
