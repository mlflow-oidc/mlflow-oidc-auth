import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { ModelListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import { useSearch } from "../../core/hooks/use-search";
import { usePagedList } from "../../core/hooks/use-paged-list";
import { fetchModelsPage } from "../../core/services/entity-service";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityNameLink } from "../../shared/components/entity-name-link";
import { buildEntityRoute } from "../../shared/utils/string-utils";

export default function ModelsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, items, pagination } = usePagedList(
    fetchModelsPage,
    submittedTerm,
  );

  const getRowHref = (model: ModelListItem) =>
    buildEntityRoute("/models", model.name);

  const columns: ColumnConfig<ModelListItem>[] = [
    {
      header: "Name",
      render: (item) => (
        <EntityNameLink to={getRowHref(item)} title={item.name}>
          {item.name}
        </EntityNameLink>
      ),
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
