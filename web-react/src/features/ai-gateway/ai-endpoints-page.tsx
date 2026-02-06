import { useAllGatewayEndpoints } from "../../core/hooks/use-all-gateway-endpoints";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { GatewayEndpointListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { RowActionButton } from "../../shared/components/row-action-button";

export default function AiEndpointsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allGatewayEndpoints } =
    useAllGatewayEndpoints();

  const endpointsList = allGatewayEndpoints || [];

  const filteredEndpoints = endpointsList.filter((endpoint) =>
    endpoint.name.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const renderPermissionsButton = (endpoint: GatewayEndpointListItem) => (
    <div className="invisible group-hover:visible">
      <RowActionButton
        entityId={endpoint.name}
        route="/ai-gateway/endpoints"
        buttonText="Manage permissions"
      />
    </div>
  );

  const columnsWithAction: ColumnConfig<GatewayEndpointListItem>[] = [
    {
      header: "Endpoint Name",
      render: (item) => item.name,
    },
    {
      header: "Type",
      render: (item) => item.type,
    },
    {
      header: "Permissions",
      render: (item) => renderPermissionsButton(item),
      className: "flex-shrink-0",
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
            data={filteredEndpoints}
            columns={columnsWithAction}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
