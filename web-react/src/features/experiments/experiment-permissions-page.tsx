import { useState } from "react";
import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import type { ColumnConfig } from "../../shared/types/table";
import type { EntityPermission, PermissionLevel, PermissionItem } from "../../shared/types/entity";
import { useSearch } from "../../core/hooks/use-search";
import { useExperimentUserPermissions } from "../../core/hooks/use-experiment-user-permissions";
import { useAllExperiments } from "../../core/hooks/use-all-experiments";
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

export default function ExperimentPermissionsPage() {
  const { experimentId: routeExperimentId } = useParams<{
    experimentId: string;
  }>();

  const experimentId = routeExperimentId || null;
  const { showToast } = useToast();

  const { isLoading, error, refresh, experimentUserPermissions } =
    useExperimentUserPermissions({ experimentId });

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

  const { allExperiments } = useAllExperiments();

  if (!experimentId) {
    return <div>Experiment ID is required.</div>;
  }

  const handleEditClick = (item: EntityPermission) => {
    // Convert EntityPermission to PermissionItem format for the modal
    setEditingItem({
      name: item.username,
      permission: item.permission,
      type: item.kind,
      id: experimentId,
    });
    setIsModalOpen(true);
  };

  const handleSavePermission = async (newPermission: PermissionLevel) => {
    if (!editingItem) return;

    setIsSaving(true);
    try {
      const url = DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(editingItem.name, experimentId);

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
      const url = DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(item.username, experimentId);

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

  const experimentPermissionsColumns: ColumnConfig<EntityPermission>[] = [
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

  const permissionsList = experimentUserPermissions || [];

  const filteredPermissions = permissionsList.filter((p) =>
    p.username.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const experiment = allExperiments?.find((e) => e.id === experimentId);
  const experimentName = experiment?.name || experimentId;

  return (
    <PageContainer title={`Permissions for Experiment ${experimentName}`}>
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
            columns={experimentPermissionsColumns}
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
        type="experiments"
        isLoading={isSaving}
      />
    </PageContainer>
  );
}
