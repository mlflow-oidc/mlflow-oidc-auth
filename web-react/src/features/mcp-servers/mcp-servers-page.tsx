import { usePagedList } from "../../core/hooks/use-paged-list";
import { fetchMcpServersPage } from "../../core/services/mcp-server-service";
import { useSearch } from "../../core/hooks/use-search";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import type { McpServerListItem } from "../../shared/types/entity";
import type { ColumnConfig } from "../../shared/types/table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { EntityNameLink } from "../../shared/components/entity-name-link";
import { buildEntityRoute } from "../../shared/utils/string-utils";

export default function McpServersPage() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, items, pagination } = usePagedList(
    fetchMcpServersPage,
    submittedTerm,
  );

  // Names are "<namespace>/<slug>": buildEntityRoute keeps the "/" inside one path segment.
  const getRowHref = (server: McpServerListItem) =>
    buildEntityRoute("/mcp-servers", server.name);

  const columns: ColumnConfig<McpServerListItem>[] = [
    {
      header: "Server Name",
      render: (item) => (
        <EntityNameLink to={getRowHref(item)} title={item.name}>
          {item.name}
        </EntityNameLink>
      ),
    },
    {
      header: "Display Name",
      render: (item) => item.display_name ?? "",
    },
    {
      header: "Latest Version",
      render: (item) => item.latest_version ?? "",
    },
  ];

  return (
    <PageContainer title="MCP Servers">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading MCP servers..."
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
              placeholder="Search MCP servers..."
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
