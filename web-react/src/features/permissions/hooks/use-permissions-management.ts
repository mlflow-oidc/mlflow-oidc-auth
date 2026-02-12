import { useState, useCallback } from "react";
import { request } from "../../../core/services/api-utils";
import { useToast } from "../../../shared/components/toast/use-toast";
import { DYNAMIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";
import type {
  EntityPermission,
  PermissionLevel,
  PermissionItem,
  PermissionType,
} from "../../../shared/types/entity";

interface UsePermissionsManagementProps {
  resourceId: string;
  resourceType: PermissionType;
  refresh: () => void;
}

export function usePermissionsManagement({
  resourceId,
  resourceType,
  refresh,
}: UsePermissionsManagementProps) {
  const { showToast } = useToast();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<PermissionItem | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  const handleEditClick = useCallback((item: EntityPermission) => {
    setEditingItem({
      name: item.name,
      permission: item.permission,
      kind: item.kind,
    });
    setIsModalOpen(true);
  }, []);

  const handleSavePermission = useCallback(
    async (newPermission: PermissionLevel) => {
      if (!editingItem) return;

      setIsSaving(true);
      try {
        let url = "";
        if (resourceType === "experiments") {
          url =
            editingItem.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PERMISSION(
                  editingItem.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(
                  editingItem.name,
                  resourceId,
                );
        } else if (resourceType === "models") {
          url =
            editingItem.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PERMISSION(
                  editingItem.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_MODEL_PERMISSION(
                  editingItem.name,
                  resourceId,
                );
        } else if (resourceType === "prompts") {
          url =
            editingItem.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PERMISSION(
                  editingItem.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(
                  editingItem.name,
                  resourceId,
                );
        } else if (resourceType === "endpoints") {
          url =
            editingItem.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PERMISSION(
                  editingItem.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PERMISSION(
                  editingItem.name,
                  resourceId,
                );
        } else if (resourceType === "ai-secrets") {
          url =
            editingItem.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PERMISSION(
                  editingItem.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PERMISSION(
                  editingItem.name,
                  resourceId,
                );
        } else if (resourceType === "ai-models") {
          url =
            editingItem.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PERMISSION(
                  editingItem.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PERMISSION(
                  editingItem.name,
                  resourceId,
                );
        }

        await request(url, {
          method: "PATCH",
          body: JSON.stringify({ permission: newPermission }),
        });

        showToast(
          `Permission for ${editingItem.name} has been updated`,
          "success",
        );
        refresh();
        setIsModalOpen(false);
        setEditingItem(null);
      } catch {
        showToast("Failed to update permission", "error");
      } finally {
        setIsSaving(false);
      }
    },
    [editingItem, resourceId, resourceType, refresh, showToast],
  );

  const handleRemovePermission = useCallback(
    async (item: EntityPermission) => {
      try {
        let url = "";
        if (resourceType === "experiments") {
          url =
            item.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PERMISSION(
                  item.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(
                  item.name,
                  resourceId,
                );
        } else if (resourceType === "models") {
          url =
            item.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PERMISSION(
                  item.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_MODEL_PERMISSION(
                  item.name,
                  resourceId,
                );
        } else if (resourceType === "prompts") {
          url =
            item.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PERMISSION(
                  item.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(
                  item.name,
                  resourceId,
                );
        } else if (resourceType === "endpoints") {
          url =
            item.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PERMISSION(
                  item.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PERMISSION(
                  item.name,
                  resourceId,
                );
        } else if (resourceType === "ai-secrets") {
          url =
            item.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PERMISSION(
                  item.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PERMISSION(
                  item.name,
                  resourceId,
                );
        } else if (resourceType === "ai-models") {
          url =
            item.kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PERMISSION(
                  item.name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PERMISSION(
                  item.name,
                  resourceId,
                );
        }

        await request(url, {
          method: "DELETE",
        });

        showToast(`Permission for ${item.name} has been removed`, "success");
        refresh();
      } catch {
        showToast("Failed to remove permission", "error");
      }
    },
    [resourceId, resourceType, refresh, showToast],
  );

  const handleModalClose = useCallback(() => {
    setIsModalOpen(false);
    setEditingItem(null);
  }, []);

  const handleGrantPermission = useCallback(
    async (
      name: string,
      permission: PermissionLevel,
      kind: "user" | "group" = "user",
    ) => {
      setIsSaving(true);
      try {
        let url = "";
        if (resourceType === "experiments") {
          url =
            kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PERMISSION(
                  name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(
                  name,
                  resourceId,
                );
        } else if (resourceType === "models") {
          url =
            kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PERMISSION(name, resourceId)
              : DYNAMIC_API_ENDPOINTS.USER_MODEL_PERMISSION(name, resourceId);
        } else if (resourceType === "prompts") {
          url =
            kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PERMISSION(name, resourceId)
              : DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(name, resourceId);
        } else if (resourceType === "endpoints") {
          url =
            kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_ENDPOINT_PERMISSION(
                  name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_GATEWAY_ENDPOINT_PERMISSION(
                  name,
                  resourceId,
                );
        } else if (resourceType === "ai-secrets") {
          url =
            kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_SECRET_PERMISSION(
                  name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_GATEWAY_SECRET_PERMISSION(
                  name,
                  resourceId,
                );
        } else if (resourceType === "ai-models") {
          url =
            kind === "group"
              ? DYNAMIC_API_ENDPOINTS.GROUP_GATEWAY_MODEL_PERMISSION(
                  name,
                  resourceId,
                )
              : DYNAMIC_API_ENDPOINTS.USER_GATEWAY_MODEL_PERMISSION(
                  name,
                  resourceId,
                );
        }

        await request(url, {
          method: "POST",
          body: JSON.stringify({ permission }),
        });

        showToast(`Permission for ${name} has been granted`, "success");
        refresh();
        return true;
      } catch {
        showToast("Failed to grant permission", "error");
        return false;
      } finally {
        setIsSaving(false);
      }
    },
    [resourceId, resourceType, refresh, showToast],
  );

  return {
    isModalOpen,
    editingItem,
    isSaving,
    handleEditClick,
    handleSavePermission,
    handleRemovePermission,
    handleModalClose,
    handleGrantPermission,
  };
}
