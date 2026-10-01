import { useState } from "react";
import {
  faIdCard,
  faKey,
  faPlus,
  faTrash,
} from "@fortawesome/free-solid-svg-icons";
import { IconButton } from "../../shared/components/icon-button";
import { EntityNameLink } from "../../shared/components/entity-name-link";
import { buildEntityRoute } from "../../shared/utils/string-utils";
import type { ColumnConfig } from "../../shared/types/table";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useSearch } from "../../core/hooks/use-search";
import { usePagedList } from "../../core/hooks/use-paged-list";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { useCurrentUser } from "../../core/hooks/use-current-user";
import { Button } from "../../shared/components/button";
import { CreateServiceAccountModal } from "./components/create-service-account-modal";
import { UserIdentitiesModal } from "../users/components/user-identities-modal";
import { ServiceAccountSourceModal } from "./components/service-account-source-modal";
import { useServiceAccountSources } from "./hooks/use-service-account-sources";
import { sourceLabel } from "./services/service-account-source-service";
import { useApi } from "../../core/hooks/use-api";
import {
  createUser,
  deleteUser,
  fetchAllUserDetails,
  fetchServiceAccountsPage,
} from "../../core/services/user-service";

const fetchServiceAccountDetails = fetchAllUserDetails(true);
import { useToast } from "../../shared/components/toast/use-toast";

export default function ServiceAccountsPage() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [identitiesUser, setIdentitiesUser] = useState<string | null>(null);
  const [sourceUser, setSourceUser] = useState<string | null>(null);
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, items, pagination } = usePagedList(
    fetchServiceAccountsPage,
    submittedTerm,
  );
  const { currentUser } = useCurrentUser();
  const { showToast } = useToast();

  const handleCreateServiceAccount = async (data: {
    name: string;
    display_name: string;
    is_admin: boolean;
    service_account_source: string;
    subject?: string;
  }) => {
    try {
      await createUser({
        username: data.name,
        display_name: data.display_name,
        is_admin: data.is_admin,
        is_service_account: true,
        service_account_source: data.service_account_source,
        ...(data.subject ? { subject: data.subject } : {}),
      });
      refetchDetails();
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
  const { sources } = useServiceAccountSources();
  const { data: details, refetch: refetchDetails } = useApi(
    fetchServiceAccountDetails,
  );
  const sourceOf = (username: string) =>
    details?.find((d) => d.username === username)?.service_account_source;

  const tableData = items.map((username) => ({
    id: username,
    username,
  }));

  const serviceAccountHref = (username: string) =>
    buildEntityRoute("/service-accounts", username, "/experiments");

  const columns: ColumnConfig<{ id: string; username: string }>[] = [
    {
      header: "Service Account Name",
      render: ({ username }) => (
        <EntityNameLink to={serviceAccountHref(username)} title={username}>
          {username}
        </EntityNameLink>
      ),
    },
    ...(isAdmin
      ? [
          {
            header: "Signs in with",
            render: ({ username }: { username: string }) =>
              sourceLabel(sourceOf(username), sources),
          },
          {
            header: "Actions",
            render: ({ username }: { username: string }) => (
              <div className="flex space-x-2">
                <IconButton
                  icon={faKey}
                  title="How it signs in"
                  muted
                  onClick={() => setSourceUser(username)}
                />
                <IconButton
                  icon={faIdCard}
                  title="Identities"
                  muted
                  onClick={() => setIdentitiesUser(username)}
                />
                <IconButton
                  icon={faTrash}
                  title="Remove service account"
                  muted
                  onClick={() => {
                    void handleRemoveServiceAccount(username);
                  }}
                />
              </div>
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
            pagination={pagination}
            columns={columns}
            searchTerm={submittedTerm}
            getRowHref={({ username }) => serviceAccountHref(username)}
          />

          <CreateServiceAccountModal
            key={isModalOpen ? "open" : "closed"}
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            sources={sources}
            onSave={(data) => {
              void handleCreateServiceAccount(data);
            }}
          />
        </>
      )}
      <UserIdentitiesModal
        username={identitiesUser}
        onClose={() => setIdentitiesUser(null)}
      />
      <ServiceAccountSourceModal
        username={sourceUser}
        currentSource={sourceUser ? sourceOf(sourceUser) : null}
        sources={sources}
        onClose={() => setSourceUser(null)}
        onSaved={refetchDetails}
      />
    </PageContainer>
  );
}
