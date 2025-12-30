import { useState, useCallback } from "react";
import { http } from "../../../core/services/http";
import { useToast } from "../../../shared/components/toast/use-toast";
import { DYNAMIC_API_ENDPOINTS } from "../../../core/configs/api-endpoints";
import type { 
    EntityPermission, 
    PermissionLevel, 
    PermissionItem, 
    PermissionType 
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
            name: item.username,
            permission: item.permission,
            type: item.kind,
        });
        setIsModalOpen(true);
    }, []);

    const handleSavePermission = useCallback(async (newPermission: PermissionLevel) => {
        if (!editingItem) return;

        setIsSaving(true);
        try {
            let url = "";
            if (resourceType === "experiments") {
                url = DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(editingItem.name, resourceId);
            } else if (resourceType === "models") {
                url = DYNAMIC_API_ENDPOINTS.USER_REGISTERED_MODEL_PERMISSION(editingItem.name, resourceId);
            } else if (resourceType === "prompts") {
                url = DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(editingItem.name, resourceId);
            }

            await http(url, {
                method: "PATCH",
                body: JSON.stringify({ permission: newPermission }),
            });

            showToast(`Permission for ${editingItem.name} has been updated.`, "success");
            refresh();
            setIsModalOpen(false);
            setEditingItem(null);
        } catch {
            showToast("Failed to update permission. Please try again.", "error");
        } finally {
            setIsSaving(false);
        }
    }, [editingItem, resourceId, resourceType, refresh, showToast]);

    const handleRemovePermission = useCallback(async (item: EntityPermission) => {
        try {
            let url = "";
            if (resourceType === "experiments") {
                url = DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(item.username, resourceId);
            } else if (resourceType === "models") {
                url = DYNAMIC_API_ENDPOINTS.USER_REGISTERED_MODEL_PERMISSION(item.username, resourceId);
            } else if (resourceType === "prompts") {
                url = DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(item.username, resourceId);
            }

            await http(url, {
                method: "DELETE",
            });

            showToast(`Permission for ${item.username} has been removed.`, "success");
            refresh();
        } catch {
            showToast("Failed to remove permission. Please try again.", "error");
        }
    }, [resourceId, resourceType, refresh, showToast]);

    const handleModalClose = useCallback(() => {
        setIsModalOpen(false);
        setEditingItem(null);
    }, []);

    const handleGrantPermission = useCallback(async (username: string, permission: PermissionLevel) => {
        setIsSaving(true);
        try {
            let url = "";
            if (resourceType === "experiments") {
                url = DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(username, resourceId);
            } else if (resourceType === "models") {
                url = DYNAMIC_API_ENDPOINTS.USER_REGISTERED_MODEL_PERMISSION(username, resourceId);
            } else if (resourceType === "prompts") {
                url = DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(username, resourceId);
            }

            await http(url, {
                method: "POST",
                body: JSON.stringify({ permission }),
            });

            showToast(`Permission for ${username} has been granted.`, "success");
            refresh();
            return true;
        } catch {
            showToast("Failed to grant permission. Please try again.", "error");
            return false;
        } finally {
            setIsSaving(false);
        }
    }, [resourceId, resourceType, refresh, showToast]);

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
