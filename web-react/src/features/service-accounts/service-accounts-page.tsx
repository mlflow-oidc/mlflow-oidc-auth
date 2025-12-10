import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useSearch } from "../../core/hooks/use-search";
import { useAllServiceAccounts } from "../../core/hooks/use-all-accounts";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";

export default function ServiceAccountsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allServiceAccounts } =
    useAllServiceAccounts();

  const serviceAccountsList = allServiceAccounts || [];

  const filteredServiceAccounts = serviceAccountsList.filter((username) =>
    username.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  return (
    <PageContainer title="Service Accounts Page">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading service accounts list..."
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
            placeholder="Search service accounts..."
          />
          <ResultsHeader count={filteredServiceAccounts.length} />
          <EntityListTable
            mode="primitive"
            data={filteredServiceAccounts}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
