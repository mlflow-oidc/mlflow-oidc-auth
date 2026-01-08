import { useState } from "react";
import { useParams, Link } from "react-router";
import PageContainer from "../../shared/components/page/page-container";
import type { PermissionType } from "../../shared/types/entity";
import { Button } from "../../shared/components/button";
import { TokenInfoBlock } from "../../shared/components/token-info-block";
import { useUserDetails } from "../../core/hooks/use-user-details";
import { useUser } from "../../core/hooks/use-user";
import { NormalPermissionsView } from "./components/normal-permissions-view";
import { RegexPermissionsView } from "./components/regex-permissions-view";

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
      title={isRegexMode ? `Regex Permissions for ${entityName}` : `Permissions for ${entityName}`}
    >
      <div className="flex items-end gap-6">
      {entityKind === "user" && currentUser?.is_admin && (
        <TokenInfoBlock
          username={entityName}
          passwordExpiration={userDetails?.password_expiration}
          onTokenGenerated={userDetailsRefetch}
        />
      )}

      {currentUser?.is_admin && (
          <Button
            variant="secondary"
            onClick={() => setIsRegexMode(!isRegexMode)}
            className="whitespace-nowrap mb-2"
          >
            Regex Mode: {isRegexMode ? "ON" : "OFF"}
          </Button>
        )}
      </div>

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
