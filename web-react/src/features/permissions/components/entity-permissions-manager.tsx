import { useSearch } from "../../../core/hooks/use-search";
import { EntityListTable } from "../../../shared/components/entity-list-table";
import PageStatus from "../../../shared/components/page/page-status";
import { SearchInput } from "../../../shared/components/search-input";
import { IconButton } from "../../../shared/components/icon-button";
import { faEdit, faTrash } from "@fortawesome/free-solid-svg-icons";
import { EditPermissionModal } from "../../users/components/edit-permission-modal";
import { usePermissionsManagement } from "../hooks/use-permissions-management";
import type { ColumnConfig } from "../../../shared/types/table";
import type {
  EntityPermission,
  PermissionType,
} from "../../../shared/types/entity";
import { useAllUsers } from "../../../core/hooks/use-all-users";
import { useAllServiceAccounts } from "../../../core/hooks/use-all-accounts";
import { useAllGroups } from "../../../core/hooks/use-all-groups";
import { Button } from "../../../shared/components/button";
import { GrantPermissionModal } from "./grant-permission-modal";
import { useState } from "react";

interface EntityPermissionsManagerProps {
  resourceId: string;
  resourceName: string;
  resourceType: PermissionType;
  permissions: EntityPermission[];
  isLoading: boolean;
  error: Error | null;
  refresh: () => void;
}

export function EntityPermissionsManager({
  resourceId,
  resourceName,
  resourceType,
  permissions,
  isLoading,
  error,
  refresh,
}: EntityPermissionsManagerProps) {
  const {
    isModalOpen,
    editingItem,
    isSaving,
    handleEditClick,
    handleSavePermission,
    handleRemovePermission,
    handleModalClose,
    handleGrantPermission,
  } = usePermissionsManagement({
    resourceId,
    resourceType,
    refresh,
  });

  const { allUsers } = useAllUsers();
  const { allServiceAccounts } = useAllServiceAccounts();
  const { allGroups } = useAllGroups();

  const [isAddUserModalOpen, setIsAddUserModalOpen] = useState(false);
  const [isAddAccountModalOpen, setIsAddAccountModalOpen] = useState(false);
  const [isAddGroupModalOpen, setIsAddGroupModalOpen] = useState(false);

  const existingNames = new Set(permissions.map((p) => p.name));

  const availableUsers = (allUsers || []).filter(
    (username) => !existingNames.has(username),
  );
  const availableAccounts = (allServiceAccounts || []).filter(
    (username) => !existingNames.has(username),
  );
  const availableGroups = (allGroups || []).filter(
    (groupname) => !existingNames.has(groupname),
  );

  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const filteredPermissions = permissions.filter((p) =>
    p.name.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const columns: ColumnConfig<EntityPermission>[] = [
    {
      header: "Name",
      render: (item) => item.name,
    },
    {
      header: "Permission",
      render: (item) => item.permission,
    },
    {
      header: "Kind",
      render: (item) => item.kind,
    },
    {
      header: "Actions",
      render: (item) => (
        <div className="flex space-x-2">
          <IconButton
            icon={faEdit}
            title="Edit permission"
            onClick={() => handleEditClick(item)}
          />
          <IconButton
            icon={faTrash}
            title="Remove permission"
            onClick={() => void handleRemovePermission(item)}
          />
        </div>
      ),
      className: "w-24",
    },
  ];

  return (
    <>
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading permissions list..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="flex items-center space-x-2 mb-4">
            <Button
              variant="secondary"
              onClick={() => setIsAddUserModalOpen(true)}
              disabled={availableUsers.length === 0}
              title={
                availableUsers.length === 0
                  ? "All users already have permissions"
                  : "Add user permission"
              }
            >
              + Add
            </Button>
            <Button
              variant="secondary"
              onClick={() => setIsAddAccountModalOpen(true)}
              disabled={availableAccounts.length === 0}
              title={
                availableAccounts.length === 0
                  ? "All service accounts already have permissions"
                  : "Add service account permission"
              }
            >
              + Add Service Account
            </Button>
            <Button
              variant="secondary"
              onClick={() => setIsAddGroupModalOpen(true)}
              disabled={availableGroups.length === 0}
              title={
                availableGroups.length === 0
                  ? "All groups already have permissions"
                  : "Add group permission"
              }
            >
              + Add Group
            </Button>
          </div>
          <div className="mb-2">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search permissions..."
            />
          </div>

          <EntityListTable
            data={filteredPermissions}
            columns={columns}
            searchTerm={submittedTerm}
          />
        </>
      )}

      {isModalOpen && editingItem && (
        <EditPermissionModal
          isOpen={isModalOpen}
          onClose={handleModalClose}
          onSave={handleSavePermission}
          item={editingItem}
          username={editingItem?.name || ""}
          resourceId={resourceId}
          type={resourceType}
          isLoading={isSaving}
          key={editingItem.name}
        />
      )}

      {isAddUserModalOpen && (
        <GrantPermissionModal
          isOpen={isAddUserModalOpen}
          onClose={() => setIsAddUserModalOpen(false)}
          onSave={async (username, permission) => {
            const success = await handleGrantPermission(username, permission);
            if (success) setIsAddUserModalOpen(false);
          }}
          title={`Grant user permissions for ${resourceName}`}
          label="User"
          options={availableUsers}
          isLoading={isSaving}
        />
      )}

      {isAddAccountModalOpen && (
        <GrantPermissionModal
          isOpen={isAddAccountModalOpen}
          onClose={() => setIsAddAccountModalOpen(false)}
          onSave={async (username, permission) => {
            const success = await handleGrantPermission(username, permission);
            if (success) setIsAddAccountModalOpen(false);
          }}
          title={`Grant service account permissions for ${resourceName}`}
          label="Service account"
          options={availableAccounts}
          isLoading={isSaving}
        />
      )}

      {isAddGroupModalOpen && (
        <GrantPermissionModal
          isOpen={isAddGroupModalOpen}
          onClose={() => setIsAddGroupModalOpen(false)}
          onSave={async (name, permission) => {
            const success = await handleGrantPermission(
              name,
              permission,
              "group",
            );
            if (success) setIsAddGroupModalOpen(false);
          }}
          title={`Grant group permissions for ${resourceName}`}
          label="Group"
          options={availableGroups}
          isLoading={isSaving}
        />
      )}
    </>
  );
}
