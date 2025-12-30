import { useSearch } from "../../../core/hooks/use-search";
import { EntityListTable } from "../../../shared/components/entity-list-table";
import PageStatus from "../../../shared/components/page/page-status";
import ResultsHeader from "../../../shared/components/page/results-header";
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

interface EntityPermissionsManagerProps {
    resourceId: string;
    resourceType: PermissionType;
    permissions: EntityPermission[];
    isLoading: boolean;
    error: Error | null;
    refresh: () => void;
}

export function EntityPermissionsManager({
    resourceId,
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
    } = usePermissionsManagement({
        resourceId,
        resourceType,
        refresh,
    });

    const {
        searchTerm,
        submittedTerm,
        handleInputChange,
        handleSearchSubmit,
        handleClearSearch,
    } = useSearch();

    const filteredPermissions = permissions.filter((p) =>
        p.username.toLowerCase().includes(submittedTerm.toLowerCase())
    );

    const columns: ColumnConfig<EntityPermission>[] = [
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
                        columns={columns}
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
                type={resourceType}
                isLoading={isSaving}
            />
        </>
    );
}
