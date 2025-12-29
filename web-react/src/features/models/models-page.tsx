import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { ModelListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import { useSearch } from "../../core/hooks/use-search";
import { useAllModels } from "../../core/hooks/use-all-models";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";
import { RowActionButton } from "../../shared/components/row-action-button";

const modelsColumns: ColumnConfig<ModelListItem>[] = [
  {
    header: "Name",
    render: (item) => item.name,
  },
  {
    header: "Description",
    render: (item) => item.description,
  },
];

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
    ...modelsColumns,
    {
      header: "Permissions",
      render: (item) => renderPermissionsButton(item),
      className: "flex-shrink-0",
    },
  ];

  return (
    <PageContainer title="Models Page">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading models list..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <SearchInput
            value={searchTerm}
            onInputChange={handleInputChange}
            onSubmit={handleSearchSubmit}
            onClear={handleClearSearch}
            placeholder="Search models..."
          />
          <ResultsHeader count={filteredModels.length} />
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
