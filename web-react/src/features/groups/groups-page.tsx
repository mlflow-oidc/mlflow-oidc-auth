import { useMemo, useState } from "react";
import { SearchInput } from "../../shared/components/search-input";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { Button } from "../../shared/components/button";
import { useSearch } from "../../core/hooks/use-search";
import { useAllGroups } from "../../core/hooks/use-all-groups";
import { useAllGroupDetails } from "../../core/hooks/use-all-group-details";
import { useUser } from "../../core/hooks/use-user";
import { RowActionButton } from "../../shared/components/row-action-button";
import { LifecycleBadge } from "../../shared/components/lifecycle-badge";
import { CreateGroupModal } from "./components/create-group-modal";
import type { ColumnConfig } from "../../shared/types/table";
import type { GroupDetails } from "../../shared/types/entity";

const renderPermissionsButton = (groupName: string) => (
  <div className="invisible group-hover:visible">
    <RowActionButton
      entityId={groupName}
      suffix="/experiments"
      route="/groups"
      buttonText="Manage permissions"
    />
  </div>
);

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

  const { isLoading, error, refresh, allGroups } = useAllGroups();

  const groupsList = allGroups || [];

  const filteredGroups = groupsList.filter((group) =>
    group.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const tableData = filteredGroups.map((group) => ({
    id: group,
    groupName: group,
  }));

  const columnsWithAction: ColumnConfig<{ id: string; groupName: string }>[] = [
    {
      header: "Group Name",
      render: ({ groupName }) => (
        <span className="truncate block" title={groupName}>
          {groupName}
        </span>
      ),
    },
    {
      header: "Permissions",
      render: ({ groupName }) => renderPermissionsButton(groupName),
      className: "flex-shrink-0",
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
            searchTerm={submittedTerm}
            columns={columnsWithAction}
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

  const { groups, isLoading, error, refresh } = useAllGroupDetails();

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const filteredGroups = useMemo(
    () =>
      groups.filter((group) =>
        group.group_name.toLowerCase().includes(submittedTerm.toLowerCase()),
      ),
    [groups, submittedTerm],
  );

  const tableData: GroupRow[] = filteredGroups.map((group) => ({
    ...group,
    id: group.group_name,
  }));

  const columns: ColumnConfig<GroupRow>[] = [
    {
      header: "Group Name",
      render: (group) => (
        <span className="truncate block" title={group.group_name}>
          {group.group_name}
        </span>
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
    {
      header: "Permissions",
      render: (group) => renderPermissionsButton(group.group_name),
      className: "flex-shrink-0",
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
            searchTerm={submittedTerm}
            columns={columns}
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
