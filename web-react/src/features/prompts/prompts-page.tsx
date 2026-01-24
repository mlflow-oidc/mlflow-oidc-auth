import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { PromptListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import { useSearch } from "../../core/hooks/use-search";
import { useAllPrompts } from "../../core/hooks/use-all-prompts";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { RowActionButton } from "../../shared/components/row-action-button";

export default function PromptsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allPrompts } = useAllPrompts();

  const promptsList = allPrompts || [];

  const filteredPrompts = promptsList.filter((p) =>
    p.name.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const renderPermissionsButton = (prompt: PromptListItem) => (
    <div className="invisible group-hover:visible">
      <RowActionButton
        entityId={prompt.name}
        route="/prompts"
        buttonText="Manage permissions"
      />
    </div>
  );

  const columnsWithAction: ColumnConfig<PromptListItem>[] = [
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
    <PageContainer title="Prompts">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading prompts list..."
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
              placeholder="Search prompts..."
            />
          </div>

          <EntityListTable
            mode="object"
            data={filteredPrompts}
            columns={columnsWithAction}
            searchTerm={submittedTerm}
          />
        </>
      )}
    </PageContainer>
  );
}
