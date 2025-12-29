import { useState } from "react";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useSearch } from "../../core/hooks/use-search";
import { useAllServiceAccounts } from "../../core/hooks/use-all-accounts";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";
import { useCurrentUser } from "../../core/hooks/use-current-user";
import { Button } from "../../shared/components/button";
import { CreateServiceAccountModal } from "./components/create-service-account-modal";

export default function ServiceAccountsPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allServiceAccounts } =
    useAllServiceAccounts();
  const { currentUser } = useCurrentUser();

  const serviceAccountsList = allServiceAccounts || [];

  const filteredServiceAccounts = serviceAccountsList.filter((username) =>
    username.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const handleCreateServiceAccount = (data: {
    name: string;
    display_name: string;
    is_admin: boolean;
  }) => {
    console.log("Creating Service Account:", data);
    // Future API call here
  };

  const isAdmin = currentUser?.is_admin === true;

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
          {isAdmin && (
            <div className="mb-4">
              <Button
                variant="primary"
                onClick={() => setIsModalOpen(true)}
              >
                Create Service Account
              </Button>
            </div>
          )}
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

          <CreateServiceAccountModal
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            onSave={handleCreateServiceAccount}
          />
        </>
      )}
    </PageContainer>
  );
}
