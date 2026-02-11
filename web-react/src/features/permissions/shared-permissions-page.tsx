import { useState, useEffect } from "react";
import { useParams, Link } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import type { PermissionType } from "../../shared/types/entity";
import { Switch } from "../../shared/components/switch";
import { useUser } from "../../core/hooks/use-user";
import { NormalPermissionsView } from "./components/normal-permissions-view";
import { RegexPermissionsView } from "./components/regex-permissions-view";

interface SharedPermissionsPageProps {
  type: PermissionType;
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
  ];

  return (
    <PageContainer
      title={
        isRegexMode
          ? `Regex Permissions for ${entityName}`
          : `Permissions for ${entityName}`
      }
    >
      <div className="flex justify-between items-center border-b border-btn-secondary-border dark:border-btn-secondary-border-dark mb-3">
        <div className="flex space-x-4">
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
        {currentUser?.is_admin && (
          <Switch
            checked={isRegexMode}
            onChange={setIsRegexMode}
            label="Regex Mode"
            className="mr-5"
            labelClassName={`py-2 px-2 font-medium text-sm transition-colors duration-200 ${
              isRegexMode
                ? "text-btn-primary dark:text-btn-primary-dark"
                : "text-text-primary hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark hover:border-btn-secondary-border dark:hover:border-btn-secondary-border-dark"
            }`}
          />
        )}
      </div>

      {isRegexMode ? (
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
