import { useState, useEffect } from "react";
import { useParams, Link } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import {
  supportsRegexPermissions,
  type PermissionType,
} from "../../shared/types/entity";
import { Switch } from "../../shared/components/switch";
import { useUser } from "../../core/hooks/use-user";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import { NormalPermissionsView } from "./components/normal-permissions-view";
import { RegexPermissionsView } from "./components/regex-permissions-view";
import { encodeRouteParam } from "../../shared/utils/string-utils";
import { UserTokensPanel } from "../tokens/components/user-tokens-panel";

/** A permission tab, or the admin-only "tokens" tab of a user or service account. */
export type SharedPermissionsTab = PermissionType | "tokens";

interface SharedPermissionsPageProps {
  type: SharedPermissionsTab;
  baseRoute: string;
  entityKind: "user" | "group";
}

const IS_REGEX_MODE_KEY = "_mlflow_is_regex_mode";

export const SharedPermissionsPage = ({
  type,
  baseRoute,
  entityKind,
}: SharedPermissionsPageProps) => {
  const { username: routeUsername, groupName: routeGroupName } = useParams<{
    username?: string;
    groupName?: string;
  }>();

  const entityName =
    (entityKind === "user" ? routeUsername : routeGroupName) || null;

  const { currentUser } = useUser();
  const { gen_ai_gateway_enabled: genAiGatewayEnabled } = useRuntimeConfig();
  const canManageTokens = entityKind === "user" && !!currentUser?.is_admin;

  const [isRegexMode, setIsRegexMode] = useState(() => {
    const savedValue = localStorage.getItem(IS_REGEX_MODE_KEY);
    return savedValue === "true";
  });

  useEffect(() => {
    localStorage.setItem(IS_REGEX_MODE_KEY, isRegexMode.toString());
  }, [isRegexMode]);

  if (!entityName) {
    return (
      <PageContainer title="Error">
        <div className="p-4 text-red-500">
          {entityKind === "user" ? "Username" : "Group name"} is required.
        </div>
      </PageContainer>
    );
  }

  const tabs = [
    { id: "experiments", label: "Experiments" },
    { id: "models", label: "Models" },
    { id: "prompts", label: "Prompts" },
    ...(genAiGatewayEnabled
      ? [
          { id: "ai-endpoints", label: "AI\u00A0Endpoints" },
          { id: "ai-secrets", label: "AI\u00A0Secrets" },
          { id: "ai-models", label: "AI\u00A0Models" },
        ]
      : []),
    { id: "mcp-servers", label: "MCP\u00A0Servers" },
    ...(canManageTokens ? [{ id: "tokens", label: "Tokens" }] : []),
  ];

  // MCP servers have user and group grants only: no regex mode there.
  const showRegex =
    isRegexMode && type !== "tokens" && supportsRegexPermissions(type);

  return (
    <PageContainer
      title={
        type === "tokens"
          ? `Tokens for ${entityName}`
          : showRegex
            ? `Regex Permissions for ${entityName}`
            : `Permissions for ${entityName}`
      }
    >
      <div className="flex space-x-2 justify-between items-center border-b border-btn-secondary-border dark:border-btn-secondary-border-dark mb-3 min-w-0">
        <div className="flex space-x-2 overflow-x-auto whitespace-nowrap scrollbar-hide">
          {tabs.map((tab) => (
            <Link
              key={tab.id}
              to={`${baseRoute}/${encodeRouteParam(entityName)}/${tab.id}`}
              className={`py-2 px-4 border-b-2 font-medium text-sm transition-colors duration-200 shrink-0 ${
                type === tab.id
                  ? "border-btn-primary text-btn-primary dark:border-btn-primary-dark dark:text-btn-primary-dark"
                  : "border-transparent text-text-primary dark:text-text-primary-dark hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark hover:border-btn-secondary-border dark:hover:border-btn-secondary-border-dark"
              }`}
            >
              {tab.label}
            </Link>
          ))}
        </div>
        {currentUser?.is_admin &&
          type !== "tokens" &&
          supportsRegexPermissions(type) && (
          <Switch
            checked={isRegexMode}
            onChange={setIsRegexMode}
            label={"Regex\u00A0Mode"}
            className="mr-2 shrink-0"
            labelClassName={`py-2 px-2 font-medium text-sm transition-colors duration-200 ${
              isRegexMode
                ? "text-btn-primary dark:text-btn-primary-dark"
                : "text-text-primary hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark hover:border-btn-secondary-border dark:hover:border-btn-secondary-border-dark"
            }`}
          />
        )}
      </div>

      {type === "tokens" ? (
        canManageTokens && <UserTokensPanel username={entityName} />
      ) : showRegex && supportsRegexPermissions(type) ? (
        <RegexPermissionsView
          type={type}
          entityKind={entityKind}
          entityName={entityName}
        />
      ) : (
        <NormalPermissionsView
          type={type}
          entityKind={entityKind}
          entityName={entityName}
        />
      )}
    </PageContainer>
  );
};
