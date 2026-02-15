import { useAllGatewaySecrets } from "../../core/hooks/use-all-gateway-secrets";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { GatewaySecretListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { RowActionButton } from "../../shared/components/row-action-button";

export default function AiSecretsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allGatewaySecrets } =
    useAllGatewaySecrets();

  const secretsList = allGatewaySecrets || [];

  const filteredSecrets = secretsList.filter((secret) =>
    secret.key.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const renderPermissionsButton = (secret: GatewaySecretListItem) => (
    <div className="invisible group-hover:visible">
      <RowActionButton
        entityId={secret.key}
        route="/ai-gateway/secrets"
        buttonText="Manage permissions"
      />
    </div>
  );

  const columnsWithAction: ColumnConfig<GatewaySecretListItem>[] = [
    {
      header: "Secret Key",
      render: (item) => item.key,
    },
    {
      header: "Permissions",
      render: (item) => renderPermissionsButton(item),
      className: "flex-shrink-0",
    },
  ];

  return (
    <PageContainer title="AI Secrets">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading secrets list..."
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
              placeholder="Search secrets..."
            />
          </div>

          <EntityListTable
            data={filteredSecrets}
            columns={columnsWithAction}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
