import { usePagedList } from "../../core/hooks/use-paged-list";
import { fetchGatewayEndpointsPage } from "../../core/services/gateway-service";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { GatewayEndpointListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityNameLink } from "../../shared/components/entity-name-link";
import { buildEntityRoute } from "../../shared/utils/string-utils";

export default function AiEndpointsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, items, pagination } = usePagedList(
    fetchGatewayEndpointsPage,
    submittedTerm,
  );

  const getRowHref = (endpoint: GatewayEndpointListItem) =>
    buildEntityRoute("/ai-gateway/ai-endpoints", endpoint.name);

  const columns: ColumnConfig<GatewayEndpointListItem>[] = [
    {
      header: "Endpoint Name",
      render: (item) => (
        <EntityNameLink to={getRowHref(item)} title={item.name}>
          {item.name}
        </EntityNameLink>
      ),
    },
    {
      header: "Type",
      render: (item) => item.type,
    },
  ];

  return (
    <PageContainer title="AI Endpoints">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading endpoints list..."
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
              placeholder="Search endpoints..."
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
