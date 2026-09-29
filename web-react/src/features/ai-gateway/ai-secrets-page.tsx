import { usePagedList } from "../../core/hooks/use-paged-list";
import { fetchGatewaySecretsPage } from "../../core/services/gateway-service";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { GatewaySecretListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityNameLink } from "../../shared/components/entity-name-link";
import { buildEntityRoute } from "../../shared/utils/string-utils";

export default function AiSecretsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, items, pagination } = usePagedList(
    fetchGatewaySecretsPage,
    submittedTerm,
  );

  const getRowHref = (secret: GatewaySecretListItem) =>
    buildEntityRoute("/ai-gateway/secrets", secret.key);

  const columns: ColumnConfig<GatewaySecretListItem>[] = [
    {
      header: "Secret Key",
      render: (item) => (
        <EntityNameLink to={getRowHref(item)} title={item.key}>
          {item.key}
        </EntityNameLink>
      ),
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
            getRowHref={getRowHref}
            data={items}
            pagination={pagination}
            columns={columns}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
