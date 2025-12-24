import { useEffect } from "react";
import { useParams, Link } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import type { ColumnConfig } from "../../shared/types/table";
import type {
    PermissionType,
} from "../../shared/types/entity";
import { useSearch } from "../../core/hooks/use-search";
import { useUserExperimentPermissions } from "../../core/hooks/use-user-experiment-permissions";
import { useUserRegisteredModelPermissions } from "../../core/hooks/use-user-model-permissions";
import { useUserPromptPermissions } from "../../core/hooks/use-user-prompt-permissions";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";
import { SearchInput } from "../../shared/components/search-input";
import { IconButton } from "../../shared/components/icon-button";
import { faEdit, faTrash } from "@fortawesome/free-solid-svg-icons";

interface UserPermissionsPageProps {
    type: PermissionType;
}

const permissionColumns: ColumnConfig<any>[] = [
    { header: "Name", render: (item) => item.name },
    { header: "Permission", render: (item) => item.permission },
    { header: "Kind", render: (item) => item.type },
    {
        header: "Actions",
        render: (item) => (
            <div className="flex space-x-2">
                <IconButton
                    icon={faEdit}
                    title="Edit permission"
                    onClick={() => console.log(`Edit permission for: ${item.name}`)}
                />
                <IconButton
                    icon={faTrash}
                    title="Remove permission"
                    onClick={() => console.log(`Remove permission for: ${item.name}`)}
                />
            </div>
        ),
        className: "w-24",
    },
];

export default function UserPermissionsPage({ type }: UserPermissionsPageProps) {
    const { username: routeUsername } = useParams<{ username: string }>();
    const username = routeUsername || null;

    const experimentHook = useUserExperimentPermissions({ username });
    const modelHook = useUserRegisteredModelPermissions({ username });
    const promptHook = useUserPromptPermissions({ username });

    const {
        searchTerm,
        submittedTerm,
        handleInputChange,
        handleSearchSubmit,
        handleClearSearch,
    } = useSearch();

    if (!username) {
        return <div>Username is required.</div>;
    }

    const activeHook = {
        experiments: experimentHook,
        models: modelHook,
        prompts: promptHook,
    }[type];

    const { isLoading, error, refresh, permissions } = activeHook;
    const loadingText = `Loading user's ${type.replace(/s$/, "")} permissions...`;

    const filteredData = permissions.filter((p: any) =>
        p.name.toLowerCase().includes(submittedTerm.toLowerCase())
    );

    useEffect(() => {
        handleClearSearch();
    }, [type, handleClearSearch]);

    const tabs = [
        { id: "experiments", label: "Experiments" },
        { id: "models", label: "Models" },
        { id: "prompts", label: "Prompts" },
    ];

    return (
        <PageContainer title={`Permissions for ${username}`}>
            <div className="flex space-x-4 border-b border-btn-secondary-border dark:border-btn-secondary-border-dark mb-6">
                {tabs.map((tab) => (
                    <Link
                        key={tab.id}
                        to={`/users/${username}/${tab.id}`}
                        className={`py-2 px-4 border-b-2 font-medium text-sm transition-colors duration-200 ${type === tab.id
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
                    <SearchInput
                        value={searchTerm}
                        onInputChange={handleInputChange}
                        onSubmit={handleSearchSubmit}
                        onClear={handleClearSearch}
                        placeholder={`Search ${type}...`}
                    />
                    <ResultsHeader count={filteredData.length} />
                    <EntityListTable
                        mode="object"
                        data={filteredData}
                        columns={permissionColumns}
                        searchTerm={submittedTerm}
                    />
                </>
            )}
        </PageContainer>
    );
}
