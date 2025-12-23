import { useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import type { ColumnConfig } from "../../shared/types/table";
import type { ExperimentPermission } from "../../shared/types/entity";
import { useSearch } from "../../core/hooks/use-search";
import { useUserExperimentPermissions } from "../../core/hooks/use-user-experiment-permissions";
import { EntityListTable } from "../../shared/components/entity-list-table";
import PageStatus from "../../shared/components/page/page-status";
import ResultsHeader from "../../shared/components/page/results-header";
import { SearchInput } from "../../shared/components/search-input";

const userExperimentPermissionsColumns: ColumnConfig<ExperimentPermission>[] = [
    {
        header: "Name",
        render: (item) => item.name,
    },
    {
        header: "Permission",
        render: (item) => item.permission,
    },
    {
        header: "Kind",
        render: (item) => item.type,
    },
];

export default function UserPermissionsPage() {
    const { username: routeUsername } = useParams<{
        username: string;
    }>();

    const username = routeUsername || null;

    const { isLoading, error, refresh, userExperimentPermissions } =
        useUserExperimentPermissions({ username });

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

    const permissionsList = userExperimentPermissions || [];

    const filteredPermissions = permissionsList.filter((p) =>
        p.name.toLowerCase().includes(submittedTerm.toLowerCase())
    );

    return (
        <PageContainer title={`Permissions for User ${username}`}>
            <PageStatus
                isLoading={isLoading}
                loadingText="Loading user's experiment permissions..."
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
                        placeholder="Search experiments..."
                    />
                    <ResultsHeader count={filteredPermissions.length} />
                    <EntityListTable
                        mode="object"
                        data={filteredPermissions}
                        columns={userExperimentPermissionsColumns}
                        searchTerm={submittedTerm}
                    />
                </>
            )}
        </PageContainer>
    );
}
