import { useEffect } from "react";
import { Link, useParams } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { useUser } from "../../core/hooks/use-user";
import { UserDetailsCard } from "./components/user-details-card";
import { useSearch } from "../../core/hooks/use-search";
import { useUserExperimentPermissions } from "../../core/hooks/use-user-experiment-permissions";
import { useUserRegisteredModelPermissions } from "../../core/hooks/use-user-model-permissions";
import { useUserPromptPermissions } from "../../core/hooks/use-user-prompt-permissions";
import { useUserGatewayEndpointPermissions } from "../../core/hooks/use-user-gateway-endpoint-permissions";
import { useUserGatewaySecretPermissions } from "../../core/hooks/use-user-gateway-secret-permissions";
import { useUserGatewayModelPermissions } from "../../core/hooks/use-user-gateway-model-permissions";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { SearchInput } from "../../shared/components/search-input";
import type { ColumnConfig } from "../../shared/types/table";
import type { PermissionItem } from "../../shared/types/entity";
import { TokenInfoBlock } from "../../shared/components/token-info-block";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";

export const UserPage = () => {
  const { tab = "info" } = useParams<{ tab?: string }>();
  const { currentUser, isLoading: isUserLoading, error: userError } = useUser();
  const { gen_ai_gateway_enabled: genAiGatewayEnabled } = useRuntimeConfig();
  const username = currentUser?.username || null;

  const experimentHook = useUserExperimentPermissions({ username });
  const modelHook = useUserRegisteredModelPermissions({ username });
  const promptHook = useUserPromptPermissions({ username });
  const endpointHook = useUserGatewayEndpointPermissions({ username });
  const secretHook = useUserGatewaySecretPermissions({ username });
  const modelGatewayHook = useUserGatewayModelPermissions({ username });

  const activeHook =
    {
      info: null,
      experiments: experimentHook,
      models: modelHook,
      prompts: promptHook,
      endpoints: endpointHook,
      "ai-secrets": secretHook,
      "ai-models": modelGatewayHook,
    }[
      tab as
        | "info"
        | "experiments"
        | "models"
        | "prompts"
        | "endpoints"
        | "ai-secrets"
        | "ai-models"
    ] || null;

  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  useEffect(() => {
    handleClearSearch();
  }, [tab, handleClearSearch]);

  const tabs = [
    { id: "info", label: "Info" },
    { id: "experiments", label: "Experiments" },
    { id: "prompts", label: "Prompts" },
    { id: "models", label: "Models" },
    ...(genAiGatewayEnabled
      ? [
          { id: "endpoints", label: "Endpoints" },
          { id: "ai-secrets", label: "AI\u00A0Secrets" },
          { id: "ai-models", label: "AI\u00A0Models" },
        ]
      : []),
  ];

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
  ];

  const isLoading = isUserLoading || (activeHook?.isLoading ?? false);
  const error = userError || (activeHook?.error ?? null);

  const filteredPermissions =
    activeHook?.permissions.filter((p: PermissionItem) =>
      p.name.toLowerCase().includes(submittedTerm.toLowerCase()),
    ) ?? [];

  return (
    <PageContainer title="User Page">
      {currentUser && (
        <TokenInfoBlock
          username={currentUser.username}
          passwordExpiration={currentUser.password_expiration}
        />
      )}

      <div className="flex space-x-2 justify-between items-center border-b border-btn-secondary-border dark:border-btn-secondary-border-dark mb-3 min-w-0">
        <div className="flex space-x-2 overflow-x-auto whitespace-nowrap scrollbar-hide">
          {tabs.map((tabItem) => (
            <Link
              key={tabItem.id}
              to={`/user/${tabItem.id}`}
              className={`py-2 px-4 border-b-2 font-medium text-sm transition-colors duration-200 shrink-0 ${
                tab === tabItem.id
                  ? "border-btn-primary text-btn-primary dark:border-btn-primary-dark dark:text-btn-primary-dark"
                  : "border-transparent text-text-primary dark:text-text-primary-dark hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark hover:border-btn-secondary-border dark:hover:border-btn-secondary-border-dark"
              }`}
            >
              {tabItem.label}
            </Link>
          ))}
        </div>
      </div>

      <PageStatus
        isLoading={
          isLoading &&
          (!currentUser || (tab !== "info" && !activeHook?.permissions))
        }
        loadingText="Loading information..."
        error={error}
        onRetry={tab === "info" ? undefined : activeHook?.refresh}
      />

      {!isLoading && !error && currentUser && (
        <>
          {tab === "info" && <UserDetailsCard currentUser={currentUser} />}
          {tab !== "info" && activeHook && (
            <>
              <div className="mb-2">
                <SearchInput
                  value={searchTerm}
                  onInputChange={handleInputChange}
                  onSubmit={handleSearchSubmit}
                  onClear={handleClearSearch}
                  placeholder={`Search ${tab}...`}
                />
              </div>
              <EntityListTable
                data={filteredPermissions}
                columns={permissionColumns}
                searchTerm={submittedTerm}
              />
            </>
          )}
        </>
      )}
    </PageContainer>
  );
};

export default UserPage;
