import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
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

  return (
    <PageContainer title="Groups">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading groups list..."
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
              placeholder="Search groups..."
             />
          </div>

          <EntityListTable
            mode="primitive"
            data={filteredGroups}
            searchTerm={searchTerm}
          />
        </>
      )}
    </PageContainer>
  );
}


