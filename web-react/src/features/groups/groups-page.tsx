import { useState } from "react";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { Button } from "../../shared/components/button";
import { useSearch } from "../../core/hooks/use-search";
import { usePagedList } from "../../core/hooks/use-paged-list";
import {
  fetchGroupDetailsPage,
  fetchGroupsPage,
} from "../../core/services/entity-service";
import { useUser } from "../../core/hooks/use-user";
import { EntityNameLink } from "../../shared/components/entity-name-link";
import { buildEntityRoute } from "../../shared/utils/string-utils";
import { LifecycleBadge } from "../../shared/components/lifecycle-badge";
import { CreateGroupModal } from "./components/create-group-modal";
import type { ColumnConfig } from "../../shared/types/table";
import type { GroupDetails } from "../../shared/types/entity";

const groupHref = (groupName: string) =>
  buildEntityRoute("/groups", groupName, "/experiments");

/**
 * Non-admin view: `GET /permissions/groups/details` is admin-only, so
 * non-admins keep seeing the plain `string[]` group name list from
 * `GET /permissions/groups`.
 */
function LegacyGroupsView() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, items, pagination } = usePagedList(
    fetchGroupsPage,
    submittedTerm,
  );

  const tableData = items.map((group) => ({
    id: group,
    groupName: group,
  }));

  const columns: ColumnConfig<{ id: string; groupName: string }>[] = [
    {
      header: "Group Name",
      render: ({ groupName }) => (
        <EntityNameLink to={groupHref(groupName)} title={groupName}>
          {groupName}
        </EntityNameLink>
      ),
    },
  ];

  return (
    <PageContainer title="Groups">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading groups list..."
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
              placeholder="Search groups..."
            />
          </div>

          <EntityListTable
            data={tableData}
            pagination={pagination}
            searchTerm={submittedTerm}
            columns={columns}
            getRowHref={({ groupName }) => groupHref(groupName)}
          />
        </>
      )}
    </PageContainer>
  );
}

type GroupRow = GroupDetails & { id: string };

/**
 * Admin view: member count and directory source (issue #320).
 */
function AdminGroupsView() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const {
    items: groups,
    pagination,
    isLoading,
    error,
    refresh,
  } = usePagedList(fetchGroupDetailsPage, submittedTerm);

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const tableData: GroupRow[] = groups.map((group) => ({
    ...group,
    id: group.group_name,
  }));

  const columns: ColumnConfig<GroupRow>[] = [
    {
      header: "Group Name",
      render: (group) => (
        <EntityNameLink
          to={groupHref(group.group_name)}
          title={group.group_name}
        >
          {group.group_name}
        </EntityNameLink>
      ),
    },
    {
      header: "Members",
      render: (group) => (
        <span className="tabular-nums">{group.member_count}</span>
      ),
    },
    {
      header: "Source",
      render: (group) => (
        <LifecycleBadge
          variant="managed_by"
          managedBy={group.external_id ? "scim" : "manual"}
        />
      ),
    },
  ];

  return (
    <PageContainer title="Groups">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading groups list..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="flex items-center justify-between mb-2 gap-2">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search groups..."
            />
            <Button
              variant="secondary"
              onClick={() => setIsCreateModalOpen(true)}
              title="Create a group without waiting for a member to sign in"
            >
              + Create group
            </Button>
          </div>

          <EntityListTable
            data={tableData}
            pagination={pagination}
            searchTerm={submittedTerm}
            columns={columns}
            getRowHref={(group) => groupHref(group.group_name)}
          />
        </>
      )}

      {isCreateModalOpen && (
        <CreateGroupModal
          isOpen={isCreateModalOpen}
          onClose={() => setIsCreateModalOpen(false)}
          onCreated={() => {
            setIsCreateModalOpen(false);
            refresh();
          }}
        />
      )}
    </PageContainer>
  );
}

export default function GroupsPage() {
  const { currentUser } = useUser();
  const isAdmin = currentUser?.is_admin ?? false;

  return isAdmin ? <AdminGroupsView /> : <LegacyGroupsView />;
}
