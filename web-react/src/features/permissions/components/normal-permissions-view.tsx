import { useState, useEffect } from "react";
import { request } from "../../../core/services/api-utils";
import { useToast } from "../../../shared/components/toast/use-toast";
import { getPermissionUrl } from "../utils/permission-utils";
import { EditPermissionModal } from "../../users/components/edit-permission-modal";
import { useUserExperimentPermissions } from "../../../core/hooks/use-user-experiment-permissions";
import { useUserRegisteredModelPermissions } from "../../../core/hooks/use-user-model-permissions";
import { useUserPromptPermissions } from "../../../core/hooks/use-user-prompt-permissions";
import { useGroupExperimentPermissions } from "../../../core/hooks/use-group-experiment-permissions";
import { useGroupRegisteredModelPermissions } from "../../../core/hooks/use-group-model-permissions";
import { useGroupPromptPermissions } from "../../../core/hooks/use-group-prompt-permissions";
import { useUserGatewayEndpointPermissions } from "../../../core/hooks/use-user-gateway-endpoint-permissions";
import { useGroupGatewayEndpointPermissions } from "../../../core/hooks/use-group-gateway-endpoint-permissions";
import { useUserGatewaySecretPermissions } from "../../../core/hooks/use-user-gateway-secret-permissions";
import { useGroupGatewaySecretPermissions } from "../../../core/hooks/use-group-gateway-secret-permissions";
import { useUserGatewayModelPermissions } from "../../../core/hooks/use-user-gateway-model-permissions";
import { useGroupGatewayModelPermissions } from "../../../core/hooks/use-group-gateway-model-permissions";
import { useAllGatewayEndpoints } from "../../../core/hooks/use-all-gateway-endpoints";
import { useAllGatewaySecrets } from "../../../core/hooks/use-all-gateway-secrets";
import { useAllGatewayModels } from "../../../core/hooks/use-all-gateway-models";
import { EntityListTable } from "../../../shared/components/entity-list-table";
import PageStatus from "../../../shared/components/page/page-status";
import { SearchInput } from "../../../shared/components/search-input";
import { IconButton } from "../../../shared/components/icon-button";
import { faEdit, faTrash, faPlus } from "@fortawesome/free-solid-svg-icons";
import type {
  PermissionType,
  PermissionItem,
  PermissionLevel,
  ExperimentPermission,
} from "../../../shared/types/entity";
import type { ColumnConfig } from "../../../shared/types/table";
import { useSearch } from "../../../core/hooks/use-search";
import { useAllExperiments } from "../../../core/hooks/use-all-experiments";
import { useAllModels } from "../../../core/hooks/use-all-models";
import { useAllPrompts } from "../../../core/hooks/use-all-prompts";
import { GrantPermissionModal } from "./grant-permission-modal";
import { Button } from "../../../shared/components/button";

interface NormalPermissionsViewProps {
  type: PermissionType;
  entityKind: "user" | "group";
  entityName: string;
}

export const NormalPermissionsView = ({
  type,
  entityKind,
  entityName,
}: NormalPermissionsViewProps) => {
  const { showToast } = useToast();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<PermissionItem | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isGrantModalOpen, setIsGrantModalOpen] = useState(false);

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

  const userExperimentHook = useUserExperimentPermissions({
    username: entityKind === "user" ? entityName : null,
  });
  const userModelHook = useUserRegisteredModelPermissions({
    username: entityKind === "user" ? entityName : null,
  });
  const userPromptHook = useUserPromptPermissions({
    username: entityKind === "user" ? entityName : null,
  });

  const groupExperimentHook = useGroupExperimentPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });
  const groupModelHook = useGroupRegisteredModelPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });
  const groupPromptHook = useGroupPromptPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });
  const userGatewayEndpointHook = useUserGatewayEndpointPermissions({
    username: entityKind === "user" ? entityName : null,
  });
  const groupGatewayEndpointHook = useGroupGatewayEndpointPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });
  const userGatewaySecretHook = useUserGatewaySecretPermissions({
    username: entityKind === "user" ? entityName : null,
  });
  const groupGatewaySecretHook = useGroupGatewaySecretPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });
  const userGatewayModelHook = useUserGatewayModelPermissions({
    username: entityKind === "user" ? entityName : null,
  });
  const groupGatewayModelHook = useGroupGatewayModelPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });

  const activeHook =
    entityKind === "user"
      ? {
          experiments: userExperimentHook,
          models: userModelHook,
          prompts: userPromptHook,
          "ai-endpoints": userGatewayEndpointHook,
          "ai-secrets": userGatewaySecretHook,
          "ai-models": userGatewayModelHook,
        }[type]
      : {
          experiments: groupExperimentHook,
          models: groupModelHook,
          prompts: groupPromptHook,
          "ai-endpoints": groupGatewayEndpointHook,
          "ai-secrets": groupGatewaySecretHook,
          "ai-models": groupGatewayModelHook,
        }[type];

  const { isLoading, error, refresh, permissions } = activeHook;

  const { allExperiments } = useAllExperiments();
  const { allModels } = useAllModels();
  const { allPrompts } = useAllPrompts();
  const { allGatewayEndpoints } = useAllGatewayEndpoints();
  const { allGatewaySecrets } = useAllGatewaySecrets();
  const { allGatewayModels } = useAllGatewayModels();

  const getAvailableEntities = () => {
    if (type === "experiments") {
      const existingIds = new Set(
        permissions.map((p: PermissionItem) => (p as ExperimentPermission).id),
      );
      return (allExperiments || [])
        .filter((e) => !existingIds.has(e.id))
        .map((e) => ({ label: e.name, value: e.id }));
    }

    const existingNames = new Set(
      permissions.map((p: PermissionItem) => p.name),
    );
    if (type === "models") {
      return (allModels || [])
        .filter((m) => !existingNames.has(m.name))
        .map((m) => m.name);
    }
    if (type === "prompts") {
      return (allPrompts || [])
        .filter((p) => !existingNames.has(p.name))
        .map((p) => p.name);
    }
    if (type === "ai-endpoints") {
      return (allGatewayEndpoints || [])
        .filter((e) => !existingNames.has(e.name))
        .map((e) => e.name);
    }
    if (type === "ai-secrets") {
      return (allGatewaySecrets || [])
        .filter((s) => !existingNames.has(s.key))
        .map((s) => s.key);
    }
    if (type === "ai-models") {
      return (allGatewayModels || [])
        .filter((m) => !existingNames.has(m.name))
        .map((m) => m.name);
    }
    return [];
  };

  const availableEntities = getAvailableEntities();

  const handleEditClick = (item: PermissionItem) => {
    setEditingItem(item);
    setIsModalOpen(true);
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
    setEditingItem(null);
  };

  const handleSavePermission = async (newPermission: PermissionLevel) => {
    if (!entityName || !editingItem) return;

    setIsSaving(true);
    try {
      const identifier =
        "id" in editingItem ? String(editingItem.id) : editingItem.name;

      const url = getPermissionUrl({
        entityKind,
        entityName,
        type,
        identifier,
      });

      const isTargetType =
        entityKind === "user"
          ? editingItem.kind === "user" ||
            editingItem.kind === "service-account"
          : editingItem.kind === "group";
      const isCreate = !isTargetType;
      const method = isCreate ? "POST" : "PATCH";

      await request(url, {
        method,
        body: JSON.stringify({ permission: newPermission }),
      });

      showToast(
        `Permission for ${editingItem.name} has been updated`,
        "success",
      );
      refresh();
      handleModalClose();
    } catch {
      showToast("Failed to update permission", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleGrantPermission = async (
    identifier: string,
    permission: PermissionLevel,
  ) => {
    if (!entityName) return;

    setIsSaving(true);
    try {
      const url = getPermissionUrl({
        entityKind: "group",
        entityName,
        type,
        identifier,
      });

      await request(url, {
        method: "POST",
        body: JSON.stringify({ permission }),
      });

      const entityDisplayName =
        type === "experiments"
          ? allExperiments?.find((e) => e.id === identifier)?.name || identifier
          : identifier;

      showToast(
        `Permission for ${entityDisplayName} has been granted`,
        "success",
      );
      refresh();
      setIsGrantModalOpen(false);
    } catch {
      showToast("Failed to grant permission", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemovePermission = async (item: PermissionItem) => {
    if (!entityName) return;

    try {
      const identifier = "id" in item ? item.id : item.name;
      const url = getPermissionUrl({
        entityKind,
        entityName,
        type,
        identifier: String(identifier),
      });

      await request(url, {
        method: "DELETE",
      });

      showToast(`Permission for ${item.name} has been removed`, "success");
      refresh();
    } catch {
      showToast("Failed to remove permission", "error");
    }
  };

  const permissionColumns: ColumnConfig<PermissionItem>[] = [
    {
      header: "Name",
      render: (item) => (
        <span className="truncate block" title={item.name}>
          {item.name}
        </span>
      ),
    },
    { header: "Permission", render: (item) => item.permission },
    { header: "Kind", render: (item) => item.kind },
    {
      header: "Actions",
      render: (item) => {
        const isFallback = item.kind === "fallback";
        const isTargetType =
          entityKind === "user"
            ? item.kind === "user" || item.kind === "service-account"
            : item.kind === "group";
        const isCreate = !isTargetType || isFallback;
        const editIcon = isCreate ? faPlus : faEdit;
        const deleteDisabled = !isTargetType;

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

  const filteredData = permissions.filter((p: PermissionItem) =>
    p.name.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  return (
    <>
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading permissions..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mt-2 mb-3 flex items-center gap-6">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder={`Search ${type}...`}
            />
            {entityKind === "group" && (
              <Button
                variant="secondary"
                onClick={() => setIsGrantModalOpen(true)}
                disabled={availableEntities.length === 0}
                icon={faPlus}
                className="whitespace-nowrap h-8 mb-1 mt-2"
              >
                Add{" "}
                {type === "experiments"
                  ? "experiment"
                  : type === "models"
                    ? "model"
                    : type === "prompts"
                      ? "prompt"
                      : type === "ai-secrets"
                        ? "secret"
                        : type === "ai-models"
                          ? "AI model"
                          : "AI endpoint"}
              </Button>
            )}
          </div>
          <EntityListTable
            data={filteredData}
            columns={permissionColumns}
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
          username={entityName}
          type={type}
          isLoading={isSaving}
          key={"id" in editingItem ? String(editingItem.id) : editingItem.name}
        />
      )}

      <GrantPermissionModal
        isOpen={isGrantModalOpen}
        onClose={() => setIsGrantModalOpen(false)}
        onSave={(identifier, permission) =>
          handleGrantPermission(identifier, permission)
        }
        title={`Grant ${
          type === "experiments"
            ? "experiment"
            : type === "models"
              ? "model"
              : type === "prompts"
                ? "prompt"
                : type === "ai-secrets"
                  ? "secret"
                  : type === "ai-models"
                    ? "AI model"
                    : "AI Endpoint"
        } permissions for ${entityName}`}
        label={
          type === "experiments"
            ? "Experiment"
            : type === "models"
              ? "Model"
              : type === "prompts"
                ? "Prompt"
                : type === "ai-secrets"
                  ? "Secret"
                  : type === "ai-models"
                    ? "AI Model"
                    : "AI Endpoint"
        }
        options={availableEntities}
        type={type}
        isLoading={isSaving}
        key={isGrantModalOpen ? "open" : "closed"}
      />
    </>
  );
};
