import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { ModelListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import { useSearch } from "../../core/hooks/use-search";
import { useAllModels } from "../../core/hooks/use-all-models";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { RowActionButton } from "../../shared/components/row-action-button";

export default function ModelsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allModels } = useAllModels();

  const modelsList = allModels || [];

  const filteredModels = modelsList.filter((m) =>
    m.name.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const renderPermissionsButton = (model: ModelListItem) => (
    <div className="invisible group-hover:visible">
      <RowActionButton
        entityId={model.name}
        route="/models"
        buttonText="Manage permissions"
      />
    </div>
  );

  const columnsWithAction: ColumnConfig<ModelListItem>[] = [
    {
      header: "Name",
      render: (item) => item.name,
    },
    {
      header: "Permissions",
      render: (item) => renderPermissionsButton(item),
      className: "flex-shrink-0",
    },
  ];

  return (
    <PageContainer title="Models">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading models list..."
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
              placeholder="Search models..."
             />
          </div>

          <EntityListTable
            mode="object"
            data={filteredModels}
            columns={columnsWithAction}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
