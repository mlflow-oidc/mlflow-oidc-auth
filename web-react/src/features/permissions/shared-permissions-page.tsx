/* eslint-disable @typescript-eslint/no-unsafe-argument */
/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-return */
/* eslint-disable @typescript-eslint/no-explicit-any */
/* eslint-disable @typescript-eslint/no-unsafe-call */
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
import { useGroupExperimentPermissions } from "../../core/hooks/use-group-experiment-permissions";
import { useGroupRegisteredModelPermissions } from "../../core/hooks/use-group-model-permissions";
import { useGroupPromptPermissions } from "../../core/hooks/use-group-prompt-permissions";
import { useUserExperimentPatternPermissions } from "../../core/hooks/use-user-experiment-pattern-permissions";
import { useUserModelPatternPermissions } from "../../core/hooks/use-user-model-pattern-permissions";
import { useUserPromptPatternPermissions } from "../../core/hooks/use-user-prompt-pattern-permissions";
import { useGroupExperimentPatternPermissions } from "../../core/hooks/use-group-experiment-pattern-permissions";
import { useGroupModelPatternPermissions } from "../../core/hooks/use-group-model-pattern-permissions";
import { useGroupPromptPatternPermissions } from "../../core/hooks/use-group-prompt-pattern-permissions";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageStatus from "../../shared/components/page/page-status";
import { SearchInput } from "../../shared/components/search-input";
import { IconButton } from "../../shared/components/icon-button";
import { Button } from "../../shared/components/button";
import { faEdit, faTrash, faPlus } from "@fortawesome/free-solid-svg-icons";
import { TokenInfoBlock } from "../../shared/components/token-info-block";
import { useUserDetails } from "../../core/hooks/use-user-details";

import { useUser } from "../../core/hooks/use-user";

interface SharedPermissionsPageProps {
  type: PermissionType;
  baseRoute: string;
  entityKind: "user" | "group";
}

export const SharedPermissionsPage = ({
  type,
  baseRoute,
  entityKind,
}: SharedPermissionsPageProps) => {
  const { username: routeUsername, groupName: routeGroupName } = useParams<{
    username?: string;
    groupName?: string;
  }>();

  const entityName = (entityKind === "user" ? routeUsername : routeGroupName) || null;

  const { currentUser } = useUser();
  const { user: userDetails, refetch: userDetailsRefetch } = useUserDetails({
    username: entityKind === "user" && currentUser?.is_admin ? entityName : null,
  });

  const [isRegexMode, setIsRegexMode] = useState(false);

  const userExperimentHook = useUserExperimentPermissions({
    username: entityKind === "user" && !isRegexMode ? entityName : null,
  });
  const userModelHook = useUserRegisteredModelPermissions({
    username: entityKind === "user" && !isRegexMode ? entityName : null,
  });
  const userPromptHook = useUserPromptPermissions({
    username: entityKind === "user" && !isRegexMode ? entityName : null,
  });

  const groupExperimentHook = useGroupExperimentPermissions({
    groupName: entityKind === "group" && !isRegexMode ? entityName : null,
  });
  const groupModelHook = useGroupRegisteredModelPermissions({
    groupName: entityKind === "group" && !isRegexMode ? entityName : null,
  });
  const groupPromptHook = useGroupPromptPermissions({
    groupName: entityKind === "group" && !isRegexMode ? entityName : null,
  });

  // Pattern permission hooks for Regex Mode
  const userExperimentPatternHook = useUserExperimentPatternPermissions({
    username: entityKind === "user" && isRegexMode ? entityName : null,
  });
  const userModelPatternHook = useUserModelPatternPermissions({
    username: entityKind === "user" && isRegexMode ? entityName : null,
  });
  const userPromptPatternHook = useUserPromptPatternPermissions({
    username: entityKind === "user" && isRegexMode ? entityName : null,
  });

  const groupExperimentPatternHook = useGroupExperimentPatternPermissions({
    groupName: entityKind === "group" && isRegexMode ? entityName : null,
  });
  const groupModelPatternHook = useGroupModelPatternPermissions({
    groupName: entityKind === "group" && isRegexMode ? entityName : null,
  });
  const groupPromptPatternHook = useGroupPromptPatternPermissions({
    groupName: entityKind === "group" && isRegexMode ? entityName : null,
  });

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
    if (!entityName || !editingItem) return;

    setIsSaving(true);
    try {
      let url = "";
      const identifier =
        "id" in editingItem ? editingItem.id : editingItem.name;

      if (type === "experiments") {
        url =
          entityKind === "user"
            ? DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(
                entityName,
                identifier
              )
            : DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PERMISSION(
                entityName,
                identifier
              );
      } else if (type === "models") {
        url =
          entityKind === "user"
            ? DYNAMIC_API_ENDPOINTS.USER_MODEL_PERMISSION(
                entityName,
                identifier
              )
            : DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PERMISSION(
                entityName,
                identifier
              );
      } else if (type === "prompts") {
        url =
          entityKind === "user"
            ? DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(
                entityName,
                identifier
              )
            : DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PERMISSION(
                entityName,
                identifier
              );
      }

      const isCreate = editingItem.kind !== "user";
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
    if (!entityName) return;

    try {
      let url = "";
      const identifier = "id" in item ? item.id : item.name;

      if (type === "experiments") {
        url =
          entityKind === "user"
            ? DYNAMIC_API_ENDPOINTS.USER_EXPERIMENT_PERMISSION(
                entityName,
                identifier
              )
            : DYNAMIC_API_ENDPOINTS.GROUP_EXPERIMENT_PERMISSION(
                entityName,
                identifier
              );
      } else if (type === "models") {
        url =
          entityKind === "user"
            ? DYNAMIC_API_ENDPOINTS.USER_MODEL_PERMISSION(
                entityName,
                identifier
              )
            : DYNAMIC_API_ENDPOINTS.GROUP_MODEL_PERMISSION(
                entityName,
                identifier
              );
      } else if (type === "prompts") {
        url =
          entityKind === "user"
            ? DYNAMIC_API_ENDPOINTS.USER_PROMPT_PERMISSION(
                entityName,
                identifier
              )
            : DYNAMIC_API_ENDPOINTS.GROUP_PROMPT_PERMISSION(
                entityName,
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

  const permissionColumns: ColumnConfig<any>[] = isRegexMode
    ? [
        { header: "Regex Pattern", render: (item) => item.regex },
        { header: "Permission", render: (item) => item.permission },
        { header: "Priority", render: (item) => item.priority },
        {
          header: "Actions",
          render: (item) => {
            return (
              <div className="flex space-x-2">
                <IconButton
                  icon={faEdit}
                  title="Edit pattern permission"
                  onClick={() => handleEditClick(item)}
                />
                <IconButton
                  icon={faTrash}
                  title="Remove pattern permission"
                  onClick={() => {
                    void handleRemovePermission(item);
                  }}
                />
              </div>
            );
          },
          className: "w-24",
        },
      ]
    : [
        { header: "Name", render: (item) => item.name },
        { header: "Permission", render: (item) => item.permission },
        { header: "Kind", render: (item) => item.kind },
        {
          header: "Actions",
          render: (item) => {
            const isFallback = item.kind === "fallback";
            const isUserType = item.kind === "user";
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

  if (!entityName) {
    return <div>{entityKind === "user" ? "Username" : "Group name"} is required.</div>;
  }

  const activeHook =
    entityKind === "user"
      ? isRegexMode
        ? {
            experiments: userExperimentPatternHook,
            models: userModelPatternHook,
            prompts: userPromptPatternHook,
          }[type]
        : {
            experiments: userExperimentHook,
            models: userModelHook,
            prompts: userPromptHook,
          }[type]
      : isRegexMode
        ? {
            experiments: groupExperimentPatternHook,
            models: groupModelPatternHook,
            prompts: groupPromptPatternHook,
          }[type]
        : {
            experiments: groupExperimentHook,
            models: groupModelHook,
            prompts: groupPromptHook,
          }[type];

  const { isLoading, error, refresh, permissions } = activeHook || {
    isLoading: false,
    error: null,
    refresh: () => {},
    permissions: [],
  };

  const loadingText = `Loading permissions...`;

  const filteredData = permissions.filter((p: any) => {
    if (isRegexMode) {
      // Pattern permissions have 'regex' field instead of 'name'
      return p.regex?.toLowerCase().includes(submittedTerm.toLowerCase());
    }
    // Regular permissions have 'name' field
    return p.name?.toLowerCase().includes(submittedTerm.toLowerCase());
  });

  const tabs = [
    { id: "experiments", label: "Experiments" },
    { id: "models", label: "Models" },
    { id: "prompts", label: "Prompts" },
  ];

  return (
    <PageContainer title={`Permissions for ${entityName}`}>
      {entityName && entityKind === "user" && currentUser?.is_admin && (
        <TokenInfoBlock
          username={entityName}
          passwordExpiration={userDetails?.password_expiration}
          onTokenGenerated={userDetailsRefetch}
        />
      )}
      <div className="flex space-x-4 border-b border-btn-secondary-border dark:border-btn-secondary-border-dark mb-3">
        {tabs.map((tab) => (
          <Link
            key={tab.id}
            to={`${baseRoute}/${entityName}/${tab.id}`}
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
          <div className="mt-2 mb-3 flex items-center gap-3">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder={`Search ${type}...`}
              />
              {currentUser?.is_admin && (
                <Button
                  variant="secondary"
                  onClick={() => setIsRegexMode(!isRegexMode)}
                  className="whitespace-nowrap h-8 mb-1 mt-2"
                >
                  Regex Mode: {isRegexMode ? "ON" : "OFF"}
                </Button>
              )}
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
        username={entityName}
        type={type}
        isLoading={isSaving}
      />
    </PageContainer>
  );
};
