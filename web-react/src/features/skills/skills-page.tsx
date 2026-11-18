import { usePagedList } from "../../core/hooks/use-paged-list";
import { fetchSkillsPage } from "../../core/services/skill-service";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { SkillListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityNameLink } from "../../shared/components/entity-name-link";
import { buildEntityRoute } from "../../shared/utils/string-utils";

export default function SkillsPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, items, pagination } = usePagedList(
    fetchSkillsPage,
    submittedTerm,
  );

  // A skill in an organization is "@<organization>/<name>": buildEntityRoute keeps the "/" inside one path segment.
  const getRowHref = (skill: SkillListItem) =>
    buildEntityRoute("/skills", skill.name);

  const columns: ColumnConfig<SkillListItem>[] = [
    {
      header: "Skill",
      render: (item) => (
        <EntityNameLink to={getRowHref(item)} title={item.name}>
          {item.name}
        </EntityNameLink>
      ),
    },
    {
      header: "Organization",
      render: (item) => item.organization ?? "",
    },
    {
      header: "Latest Version",
      render: (item) => item.latest_version ?? "",
    },
  ];

  return (
    <PageContainer title="Skills">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading skills..."
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
              placeholder="Search skills..."
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
