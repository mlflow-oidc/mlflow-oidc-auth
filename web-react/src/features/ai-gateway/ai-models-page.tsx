import { useAllGatewayModels } from "../../core/hooks/use-all-gateway-models";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { GatewayModelListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { RowActionButton } from "../../shared/components/row-action-button";

export default function AiModelsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allGatewayModels } = useAllGatewayModels();

  const modelsList = allGatewayModels || [];

  const filteredModels = modelsList.filter((model) =>
    model.name.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const renderPermissionsButton = (model: GatewayModelListItem) => (
    <div className="invisible group-hover:visible">
      <RowActionButton
        entityId={model.name}
        route="/ai-gateway/models"
        buttonText="Manage permissions"
      />
    </div>
  );

  const columnsWithAction: ColumnConfig<GatewayModelListItem>[] = [
    {
      header: "Model Name",
      render: (item) => item.name,
    },
    {
      header: "Source",
      render: (item) => item.source,
    },
    {
      header: "Permissions",
      render: (item) => renderPermissionsButton(item),
      className: "flex-shrink-0",
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
            data={filteredModels}
            columns={columnsWithAction}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
