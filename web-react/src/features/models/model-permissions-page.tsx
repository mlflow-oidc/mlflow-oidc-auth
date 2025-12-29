import { useState } from "react";
import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import type { ColumnConfig } from "../../shared/types/table";
import type { EntityPermission, PermissionLevel, PermissionItem } from "../../shared/types/entity";
import { useSearch } from "../../core/hooks/use-search";
import { useModelUserPermissions } from "../../core/hooks/use-model-user-permissions";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";
import { SearchInput } from "../../shared/components/search-input";
import { IconButton } from "../../shared/components/icon-button";
import { faEdit, faTrash } from "@fortawesome/free-solid-svg-icons";
import { EditPermissionModal } from "../users/components/edit-permission-modal";
import { useToast } from "../../shared/components/toast/use-toast";
import { http } from "../../core/services/http";
import { DYNAMIC_API_ENDPOINTS } from "../../core/configs/api-endpoints";

export default function ModelPermissionsPage() {
  const { modelName } = useParams<{
    modelName: string;
  }>();

  const { showToast } = useToast();

  const { isLoading, error, refresh, modelUserPermissions } =
    useModelUserPermissions({ modelName: modelName || null });

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<PermissionItem | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  if (!modelName) {
    return <div>Model Name is required.</div>;
  }

  const handleEditClick = (item: EntityPermission) => {
    setEditingItem({
      name: item.username,
      permission: item.permission,
      type: item.kind,
    });
    setIsModalOpen(true);
  };

  const handleSavePermission = async (newPermission: PermissionLevel) => {
    if (!editingItem) return;

    setIsSaving(true);
    try {
      const url = DYNAMIC_API_ENDPOINTS.USER_REGISTERED_MODEL_PERMISSION(editingItem.name, modelName);

      await http(url, {
        method: "PATCH",
        body: JSON.stringify({ permission: newPermission }),
      });

      showToast(`Permission for ${editingItem.name} has been updated.`, "success");
      refresh();
      handleModalClose();
    } catch {
      showToast("Failed to update permission. Please try again.", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemovePermission = async (item: EntityPermission) => {
    try {
      const url = DYNAMIC_API_ENDPOINTS.USER_REGISTERED_MODEL_PERMISSION(item.username, modelName);

      await http(url, {
        method: "DELETE",
      });

      showToast(`Permission for ${item.username} has been removed.`, "success");
      refresh();
    } catch {
      showToast("Failed to remove permission. Please try again.", "error");
    }
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
    setEditingItem(null);
  };

  const modelPermissionsColumns: ColumnConfig<EntityPermission>[] = [
    {
      header: "Name",
      render: (item) => item.username,
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

  const permissionsList = modelUserPermissions || [];

  const filteredPermissions = permissionsList.filter((p) =>
    p.username.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  return (
    <PageContainer title={`Permissions for Model ${modelName}`}>
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading permissions list..."
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
            placeholder="Search permissions..."
          />
          <ResultsHeader count={filteredPermissions.length} />
          <EntityListTable
            mode="object"
            data={filteredPermissions}
            columns={modelPermissionsColumns}
            searchTerm={submittedTerm}
          />
        </>
      )}

      <EditPermissionModal
        isOpen={isModalOpen}
        onClose={handleModalClose}
        onSave={handleSavePermission}
        item={editingItem}
        username={editingItem?.name || ""}
        type="models"
        isLoading={isSaving}
      />
    </PageContainer>
  );
}
