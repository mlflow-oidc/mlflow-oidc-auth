import { usePagedList } from "../../core/hooks/use-paged-list";
import { fetchGatewayModelsPage } from "../../core/services/gateway-service";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { GatewayModelListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityNameLink } from "../../shared/components/entity-name-link";
import { buildEntityRoute } from "../../shared/utils/string-utils";

export default function AiModelsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, items, pagination } = usePagedList(
    fetchGatewayModelsPage,
    submittedTerm,
  );

  const getRowHref = (model: GatewayModelListItem) =>
    buildEntityRoute("/ai-gateway/models", model.name);

  const columns: ColumnConfig<GatewayModelListItem>[] = [
    {
      header: "Model Name",
      render: (item) => (
        <EntityNameLink to={getRowHref(item)} title={item.name}>
          {item.name}
        </EntityNameLink>
      ),
    },
    {
      header: "Source",
      render: (item) => item.source,
    },
  ];

  return (
    <PageContainer title="AI Models">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading AI models list..."
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
              placeholder="Search AI models..."
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
