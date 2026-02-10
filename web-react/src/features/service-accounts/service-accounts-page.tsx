import { useState } from "react";
import { faPlus, faTrash } from "@fortawesome/free-solid-svg-icons";
import { RowActionButton } from "../../shared/components/row-action-button";
import { IconButton } from "../../shared/components/icon-button";
import type { ColumnConfig } from "../../shared/types/table";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useSearch } from "../../core/hooks/use-search";
import { useAllServiceAccounts } from "../../core/hooks/use-all-accounts";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { useCurrentUser } from "../../core/hooks/use-current-user";
import { Button } from "../../shared/components/button";
import { CreateServiceAccountModal } from "./components/create-service-account-modal";
import { createUser, deleteUser } from "../../core/services/user-service";
import { useToast } from "../../shared/components/toast/use-toast";

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
  const { showToast } = useToast();

  const serviceAccountsList = allServiceAccounts || [];

  const filteredServiceAccounts = serviceAccountsList.filter((username) =>
    username.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const handleCreateServiceAccount = async (data: {
    name: string;
    display_name: string;
    is_admin: boolean;
  }) => {
    try {
      await createUser({
        username: data.name,
        display_name: data.display_name,
        is_admin: data.is_admin,
        is_service_account: true,
      });
      showToast(`Service account ${data.name} created successfully`, "success");
      refresh();
      setIsModalOpen(false);
    } catch (err) {
      console.error("Failed to create service account:", err);
      showToast("Failed to create service account", "error");
    }
  };

  const handleRemoveServiceAccount = async (username: string) => {
    try {
      await deleteUser(username);
      showToast(`Service account ${username} removed successfully`, "success");
      refresh();
    } catch (err) {
      console.error("Failed to remove service account:", err);
      showToast("Failed to remove service account", "error");
    }
  };

  const isAdmin = currentUser?.is_admin === true;

  const tableData = filteredServiceAccounts.map((username) => ({
    id: username,
    username,
  }));

  const columns: ColumnConfig<{ id: string; username: string }>[] = [
    {
      header: "Service Account Name",
      render: ({ username }) => (
        <span className="truncate block" title={username}>
          {username}
        </span>
      ),
    },
    {
      header: "Permissions",
      render: ({ username }) => (
        <div className="invisible group-hover:visible">
          <RowActionButton
            entityId={`${username}/experiments`}
            route="/service-accounts"
            buttonText="Manage permissions"
          />
        </div>
      ),
      className: "w-48",
    },
    ...(isAdmin
      ? [
          {
            header: "Actions",
            render: ({ username }: { username: string }) => (
              <IconButton
                icon={faTrash}
                title="Remove service account"
                onClick={() => {
                  void handleRemoveServiceAccount(username);
                }}
              />
            ),
            className: "w-24",
          },
        ]
      : []),
  ];

  return (
    <PageContainer title="Service Accounts">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading service accounts list..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          {isAdmin && (
            <div className="mb-2">
              <Button
                variant="secondary"
                onClick={() => setIsModalOpen(true)}
                icon={faPlus}
              >
                Create Service Account
              </Button>
            </div>
          )}
          <div className="mb-2">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search service accounts..."
            />
          </div>

          <EntityListTable
            data={tableData}
            columns={columns}
            searchTerm={submittedTerm}
          />

          <CreateServiceAccountModal
            key={isModalOpen ? "open" : "closed"}
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            onSave={(data) => {
              void handleCreateServiceAccount(data);
            }}
          />
        </>
      )}
    </PageContainer>
  );
}
