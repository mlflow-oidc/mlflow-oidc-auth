import { useEffect, useState } from "react";
import { useParams, Link } from "react-router";
import { DYNAMIC_API_ENDPOINTS } from "../../core/configs/api-endpoints";
import { http } from "../../core/services/http";
import { useToast } from "../../shared/components/toast/use-toast";
import { EditPermissionModal } from "../users/components/edit-permission-modal";
import PageContainer from "../../shared/components/page/page-container";
import type { ColumnConfig } from "../../shared/types/table";
import type {
  PermissionType,
  PermissionItem,
} from "../../shared/types/entity";
import { useSearch } from "../../core/hooks/use-search";
import { useUserExperimentPermissions } from "../../core/hooks/use-user-experiment-permissions";
import { useUserRegisteredModelPermissions } from "../../core/hooks/use-user-model-permissions";
import { useUserPromptPermissions } from "../../core/hooks/use-user-prompt-permissions";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageStatus from "../../shared/components/page/page-status";
import { SearchInput } from "../../shared/components/search-input";
import { IconButton } from "../../shared/components/icon-button";
import { faEdit, faTrash, faPlus } from "@fortawesome/free-solid-svg-icons";

interface ServiceAccountPermissionPageProps {
  type: PermissionType;
}

export default function ServiceAccountPermissionPage({
  type,
}: ServiceAccountPermissionPageProps) {
  const { username: routeUsername } = useParams<{ username: string }>();
  const username = routeUsername || null;

  const experimentHook = useUserExperimentPermissions({ username });
  const modelHook = useUserRegisteredModelPermissions({ username });
  const promptHook = useUserPromptPermissions({ username });

  const { showToast } = useToast();

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

  useEffect(() => {
    handleClearSearch();
  }, [type, handleClearSearch]);

  const handleEditClick = (item: PermissionItem) => {
    setEditingItem(item);
    setIsModalOpen(true);
  };

  const handleSavePermission = async (newPermission: string) => {
    if (!username || !editingItem) return;

    setIsSaving(true);
    try {
      let url = "";
      const identifier =
        "id" in editingItem ? editingItem.id : editingItem.name;

      if (type === "experiments") {
        url = DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(
          username,
          identifier
        );
      } else if (type === "models") {
        url = DYNAMIC_API_ENDPOINTS.USER_REGISTERED_MODEL_PERMISSION(
          username,
          identifier
        );
      } else if (type === "prompts") {
        url = DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(
          username,
          identifier
        );
      }

      const isCreate = editingItem.type !== "user";
      const method = isCreate ? "POST" : "PATCH";

      await http(url, {
        method,
        body: JSON.stringify({ permission: newPermission }),
      });

      showToast(
        `Permission for ${editingItem.name} has been updated.`,
        "success"
      );
      refresh();
      handleModalClose();
    } catch {
      showToast("Failed to update permission. Please try again.", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemovePermission = async (item: PermissionItem) => {
    if (!username) return;

    try {
      let url = "";
      const identifier = "id" in item ? item.id : item.name;

      if (type === "experiments") {
        url = DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(
          username,
          identifier
        );
      } else if (type === "models") {
        url = DYNAMIC_API_ENDPOINTS.USER_REGISTERED_MODEL_PERMISSION(
          username,
          identifier
        );
      } else if (type === "prompts") {
        url = DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(
          username,
          identifier
        );
      }

      await http(url, {
        method: "DELETE",
      });

      showToast(`Permission for ${item.name} has been removed.`, "success");
      refresh();
    } catch {
      showToast("Failed to remove permission. Please try again.", "error");
    }
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
    setEditingItem(null);
  };

  const permissionColumns: ColumnConfig<PermissionItem>[] = [
    { header: "Name", render: (item) => item.name },
    { header: "Permission", render: (item) => item.permission },
    { header: "Kind", render: (item) => item.type },
    {
      header: "Actions",
      render: (item) => {
        const isFallback = item.type === "fallback";
        const isUserType = item.type === "user";
        const isCreate = !isUserType || isFallback;
        const editIcon = isCreate ? faPlus : faEdit;
        const deleteDisabled = !isUserType;

        return (
          <div className="flex space-x-2">
            <IconButton
              icon={editIcon}
              title={isCreate ? "Add permission" : "Edit permission"}
              onClick={() => handleEditClick(item)}
            />
            <IconButton
              icon={faTrash}
              title="Remove permission"
              onClick={() => {
                void handleRemovePermission(item);
              }}
              disabled={deleteDisabled}
            />
          </div>
        );
      },
      className: "w-24",
    },
  ];

  if (!username) {
    return <div>Username is required.</div>;
  }

  const activeHook = {
    experiments: experimentHook,
    models: modelHook,
    prompts: promptHook,
  }[type];

  // Check if activeHook is defined before destructuring
  const { isLoading, error, refresh, permissions } = activeHook || {
    isLoading: false,
    error: null,
    refresh: () => {},
    permissions: [],
  };

  const loadingText = `Loading service account's ${type.replace(/s$/, "")} permissions...`;

  const filteredData = permissions.filter((p: PermissionItem) =>
    p.name.toLowerCase().includes(submittedTerm.toLowerCase())
  );

  const tabs = [
    { id: "experiments", label: "Experiments" },
    { id: "models", label: "Models" },
    { id: "prompts", label: "Prompts" },
  ];

  return (
    <PageContainer title={`Permissions for ${username}`}>
      <div className="flex space-x-4 border-b border-btn-secondary-border dark:border-btn-secondary-border-dark mb-3">
        {tabs.map((tab) => (
          <Link
            key={tab.id}
            to={`/service-accounts/${encodeURIComponent(username)}/${tab.id}`}
            className={`py-2 px-4 border-b-2 font-medium text-sm transition-colors duration-200 ${
              type === tab.id
                ? "border-btn-primary text-btn-primary dark:border-btn-primary-dark dark:text-btn-primary-dark"
                : "border-transparent text-text-primary dark:text-text-primary-dark hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark hover:border-btn-secondary-border dark:hover:border-btn-secondary-border-dark"
            }`}
          >
            {tab.label}
          </Link>
        ))}
      </div>

      <PageStatus
        isLoading={isLoading}
        loadingText={loadingText}
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mb-3 mt-2">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder={`Search ${type}...`}
            />
          </div>
          <EntityListTable
            mode="object"
            data={filteredData}
            columns={permissionColumns}
            searchTerm={submittedTerm}
          />
        </>
      )}

      <EditPermissionModal
        isOpen={isModalOpen}
        onClose={handleModalClose}
        onSave={handleSavePermission}
        item={editingItem}
        username={username}
        type={type}
        isLoading={isSaving}
      />
    </PageContainer>
  );
}
