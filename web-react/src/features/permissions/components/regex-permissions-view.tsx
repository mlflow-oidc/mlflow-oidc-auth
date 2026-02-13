import { useState, useEffect } from "react";
import { request } from "../../../core/services/api-utils";
import { getPermissionUrl } from "../utils/permission-utils";
import { useToast } from "../../../shared/components/toast/use-toast";
import { EditPermissionModal } from "../../users/components/edit-permission-modal";
import { AddRegexRuleModal } from "./add-regex-rule-modal";
import { useUserExperimentPatternPermissions } from "../../../core/hooks/use-user-experiment-pattern-permissions";
import { useUserModelPatternPermissions } from "../../../core/hooks/use-user-model-pattern-permissions";
import { useUserPromptPatternPermissions } from "../../../core/hooks/use-user-prompt-pattern-permissions";
import { useGroupExperimentPatternPermissions } from "../../../core/hooks/use-group-experiment-pattern-permissions";
import { useGroupModelPatternPermissions } from "../../../core/hooks/use-group-model-pattern-permissions";
import { useGroupPromptPatternPermissions } from "../../../core/hooks/use-group-prompt-pattern-permissions";
import { useUserGatewayEndpointPatternPermissions } from "../../../core/hooks/use-user-gateway-endpoint-pattern-permissions";
import { useGroupGatewayEndpointPatternPermissions } from "../../../core/hooks/use-group-gateway-endpoint-pattern-permissions";
import { useUserGatewaySecretPatternPermissions } from "../../../core/hooks/use-user-gateway-secret-pattern-permissions";
import { useGroupGatewaySecretPatternPermissions } from "../../../core/hooks/use-group-gateway-secret-pattern-permissions";
import { useUserGatewayModelPatternPermissions } from "../../../core/hooks/use-user-gateway-model-pattern-permissions";
import { useGroupGatewayModelPatternPermissions } from "../../../core/hooks/use-group-gateway-model-pattern-permissions";
import { EntityListTable } from "../../../shared/components/entity-list-table";
import PageStatus from "../../../shared/components/page/page-status";
import { SearchInput } from "../../../shared/components/search-input";
import { IconButton } from "../../../shared/components/icon-button";
import { Button } from "../../../shared/components/button";
import { faEdit, faTrash, faPlus } from "@fortawesome/free-solid-svg-icons";
import type {
  PermissionType,
  PatternPermissionItem,
  PermissionLevel,
} from "../../../shared/types/entity";
import type { ColumnConfig } from "../../../shared/types/table";
import { useSearch } from "../../../core/hooks/use-search";

interface RegexPermissionsViewProps {
  type: PermissionType;
  entityKind: "user" | "group";
  entityName: string;
}

export const RegexPermissionsView = ({
  type,
  entityKind,
  entityName,
}: RegexPermissionsViewProps) => {
  const { showToast } = useToast();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isRegexModalOpen, setIsRegexModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<PatternPermissionItem | null>(
    null,
  );
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

  const userExperimentPatternHook = useUserExperimentPatternPermissions({
    username: entityKind === "user" ? entityName : null,
  });
  const userModelPatternHook = useUserModelPatternPermissions({
    username: entityKind === "user" ? entityName : null,
  });
  const userPromptPatternHook = useUserPromptPatternPermissions({
    username: entityKind === "user" ? entityName : null,
  });

  const groupExperimentPatternHook = useGroupExperimentPatternPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });
  const groupModelPatternHook = useGroupModelPatternPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });
  const groupPromptPatternHook = useGroupPromptPatternPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });
  const userGatewayEndpointPatternHook =
    useUserGatewayEndpointPatternPermissions({
      username: entityKind === "user" ? entityName : null,
    });
  const groupGatewayEndpointPatternHook =
    useGroupGatewayEndpointPatternPermissions({
      groupName: entityKind === "group" ? entityName : null,
    });
  const userGatewaySecretPatternHook = useUserGatewaySecretPatternPermissions({
    username: entityKind === "user" ? entityName : null,
  });
  const groupGatewaySecretPatternHook = useGroupGatewaySecretPatternPermissions(
    {
      groupName: entityKind === "group" ? entityName : null,
    },
  );
  const userGatewayModelPatternHook = useUserGatewayModelPatternPermissions({
    username: entityKind === "user" ? entityName : null,
  });
  const groupGatewayModelPatternHook = useGroupGatewayModelPatternPermissions({
    groupName: entityKind === "group" ? entityName : null,
  });

  const activeHook =
    entityKind === "user"
      ? {
          experiments: userExperimentPatternHook,
          models: userModelPatternHook,
          prompts: userPromptPatternHook,
          endpoints: userGatewayEndpointPatternHook,
          "ai-secrets": userGatewaySecretPatternHook,
          "ai-models": userGatewayModelPatternHook,
        }[type]
      : {
          experiments: groupExperimentPatternHook,
          models: groupModelPatternHook,
          prompts: groupPromptPatternHook,
          endpoints: groupGatewayEndpointPatternHook,
          "ai-secrets": groupGatewaySecretPatternHook,
          "ai-models": groupGatewayModelPatternHook,
        }[type];

  const { isLoading, error, refresh, permissions } = activeHook;

  const handleEditClick = (item: PatternPermissionItem) => {
    setEditingItem(item);
    setIsModalOpen(true);
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
    setEditingItem(null);
  };

  const handleSavePermission = async (
    newPermission: PermissionLevel,
    regex?: string,
    priority?: number,
  ) => {
    if (!entityName || !editingItem) return;

    setIsSaving(true);
    try {
      const identifier = String(editingItem.id);

      const url = getPermissionUrl({
        entityKind,
        entityName,
        type,
        isPattern: true,
        identifier: String(identifier),
      });

      await request(url, {
        method: "PATCH",
        body: JSON.stringify({
          regex: regex ?? editingItem.regex,
          priority: priority ?? editingItem.priority,
          permission: newPermission,
        }),
      });

      showToast(
        `Permission for ${regex ?? editingItem.regex} has been updated`,
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

  const handleSaveRegexRule = async (
    regex: string,
    permission: PermissionLevel,
    priority: number,
  ) => {
    if (!entityName) return;

    setIsSaving(true);
    try {
      const url = getPermissionUrl({
        entityKind,
        entityName,
        type,
        isPattern: true,
      });

      await request(url, {
        method: "POST",
        body: JSON.stringify({ regex, permission, priority }),
      });

      showToast(`Regex rule "${regex}" has been added`, "success");
      refresh();
      setIsRegexModalOpen(false);
    } catch {
      showToast("Failed to add regex rule", "error");
    } finally {
      setIsSaving(false);
    }
  };

  const handleRemovePermission = async (item: PatternPermissionItem) => {
    if (!entityName) return;

    try {
      const identifier = String(item.id);
      const url = getPermissionUrl({
        entityKind,
        entityName,
        type,
        isPattern: true,
        identifier: String(identifier),
      });

      await request(url, {
        method: "DELETE",
      });

      showToast(`Regex rule has been removed`, "success");
      refresh();
    } catch {
      showToast("Failed to remove permission", "error");
    }
  };

  const permissionColumns: ColumnConfig<PatternPermissionItem>[] = [
    {
      header: "Regex Pattern",
      render: (item) => (
        <span className="truncate block" title={item.regex}>
          {item.regex}
        </span>
      ),
    },
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
  ];

  const filteredData = permissions.filter((p: PatternPermissionItem) =>
    p.regex?.toLowerCase().includes(submittedTerm.toLowerCase()),
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
            <Button
              variant="secondary"
              onClick={() => setIsRegexModalOpen(true)}
              icon={faPlus}
              className="whitespace-nowrap h-8 mb-1 mt-2"
            >
              Add Regex
            </Button>
          </div>
          <EntityListTable
            data={
              filteredData as (PatternPermissionItem &
                Record<string, unknown>)[]
            }
            columns={
              permissionColumns as ColumnConfig<
                PatternPermissionItem & Record<string, unknown>
              >[]
            }
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
          key={editingItem.id}
        />
      )}
      {isRegexModalOpen && (
        <AddRegexRuleModal
          isOpen={isRegexModalOpen}
          onClose={() => setIsRegexModalOpen(false)}
          onSave={handleSaveRegexRule}
          type={type}
          isLoading={isSaving}
        />
      )}
    </>
  );
};
