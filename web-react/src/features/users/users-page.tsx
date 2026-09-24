import { useCallback, useMemo, useState } from "react";
import {
  faCheck,
  faDesktop,
  faUserCheck,
  faUserSlash,
} from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { SearchInput } from "../../shared/components/search-input";
import { useAllUsers } from "../../core/hooks/use-all-users";
import { useAllUserDetails } from "../../core/hooks/use-all-user-details";
import { EntityListTable } from "../../shared/components/entity-list-table";
import { useSearch } from "../../core/hooks/use-search";
import { useUser } from "../../core/hooks/use-user";
import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { RowActionButton } from "../../shared/components/row-action-button";
import { IconButton } from "../../shared/components/icon-button";
import { Switch } from "../../shared/components/switch";
import { LifecycleBadge } from "../../shared/components/lifecycle-badge";
import { useToast } from "../../shared/components/toast/use-toast";
import { extractErrorMessage } from "../../core/services/http";
import { setUserActive } from "../../core/services/user-service";
import { DeactivateUserModal } from "./components/deactivate-user-modal";
import { UserSessionsModal } from "./components/user-sessions-modal";
import type { ColumnConfig } from "../../shared/types/table";
import type { UserDetails } from "../../shared/types/user";

const renderPermissionsButton = (username: string) => (
  <div className="invisible group-hover:visible">
    <RowActionButton
      entityId={username}
      suffix="/experiments"
      route="/users"
      buttonText="Manage permissions"
    />
  </div>
);

/**
 * Non-admin view: `GET /users/details` is admin-only, so non-admins keep
 * seeing the plain `string[]` username list from `GET /users`.
 */
function LegacyUsersView() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { isLoading, error, refresh, allUsers } = useAllUsers();

  const usersList = allUsers || [];

  const filteredUsers = usersList.filter((username) =>
    username.toLowerCase().includes(submittedTerm.toLowerCase()),
  );

  const tableData = filteredUsers.map((username) => ({
    id: username,
    username,
  }));

  const columnsWithAction: ColumnConfig<{ id: string; username: string }>[] = [
    {
      header: "Username",
      render: ({ username }) => (
        <span className="truncate block" title={username}>
          {username}
        </span>
      ),
    },
    {
      header: "Permissions",
      render: ({ username }) => renderPermissionsButton(username),
      className: "flex-shrink-0",
    },
  ];

  return (
    <PageContainer title="Users">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading users list..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mb-2">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search users..."
            />
          </div>
          <EntityListTable
            data={tableData}
            searchTerm={submittedTerm}
            columns={columnsWithAction}
          />
        </>
      )}
    </PageContainer>
  );
}

type UserRow = UserDetails & { id: string };

/**
 * Admin view: managed/inactive state plus activate/deactivate actions
 * (issue #320).
 */
function AdminUsersView() {
  const {
    searchTerm,
    submittedTerm,
    handleInputChange,
    handleSearchSubmit,
    handleClearSearch,
  } = useSearch();

  const { users, isLoading, error, refresh, updateLocalUser } =
    useAllUserDetails(false);
  const { showToast } = useToast();

  const [showInactive, setShowInactive] = useState(true);
  const [deactivatingUser, setDeactivatingUser] = useState<UserDetails | null>(
    null,
  );
  const [isDeactivating, setIsDeactivating] = useState(false);
  const [reactivatingUser, setReactivatingUser] = useState<UserDetails | null>(
    null,
  );
  const [isReactivating, setIsReactivating] = useState(false);
  const [sessionsUser, setSessionsUser] = useState<string | null>(null);

  const filteredUsers = useMemo(() => {
    return users
      .filter((user) =>
        user.username.toLowerCase().includes(submittedTerm.toLowerCase()),
      )
      .filter((user) => showInactive || user.active);
  }, [users, submittedTerm, showInactive]);

  const tableData: UserRow[] = filteredUsers.map((user) => ({
    ...user,
    id: user.username,
  }));

  const handleConfirmReactivate = useCallback(
    async (adminOverride: boolean) => {
      if (!reactivatingUser) return;
      setIsReactivating(true);
      try {
        const updated = await setUserActive(
          reactivatingUser.username,
          true,
          adminOverride,
        );
        updateLocalUser(reactivatingUser.username, updated);
        showToast(`${reactivatingUser.username} reactivated`, "success");
        setReactivatingUser(null);
      } catch (err) {
        showToast(
          extractErrorMessage(
            err,
            `Failed to reactivate ${reactivatingUser.username}`,
          ),
          "error",
        );
      } finally {
        setIsReactivating(false);
      }
    },
    [reactivatingUser, updateLocalUser, showToast],
  );

  const handleConfirmDeactivate = useCallback(
    async (adminOverride: boolean) => {
      if (!deactivatingUser) return;
      setIsDeactivating(true);
      try {
        const updated = await setUserActive(
          deactivatingUser.username,
          false,
          adminOverride,
        );
        updateLocalUser(deactivatingUser.username, updated);
        showToast(`${deactivatingUser.username} deactivated`, "success");
        setDeactivatingUser(null);
      } catch (err) {
        showToast(
          extractErrorMessage(
            err,
            `Failed to deactivate ${deactivatingUser.username}`,
          ),
          "error",
        );
      } finally {
        setIsDeactivating(false);
      }
    },
    [deactivatingUser, updateLocalUser, showToast],
  );

  const mutedClass = (active: boolean) =>
    active ? "" : "opacity-50";

  const columns: ColumnConfig<UserRow>[] = useMemo(
    () => [
      {
        header: "Username",
        render: (user) => (
          <span
            className={`truncate block ${mutedClass(user.active)}`}
            title={user.username}
          >
            {user.username}
          </span>
        ),
      },
      {
        header: "Display name",
        render: (user) => (
          <span
            className={`truncate block ${mutedClass(user.active)}`}
            title={user.display_name}
          >
            {user.display_name || "-"}
          </span>
        ),
      },
      {
        header: "State",
        render: (user) => <LifecycleBadge variant="state" active={user.active} />,
      },
      {
        header: "Managed by",
        render: (user) => (
          <LifecycleBadge variant="managed_by" managedBy={user.managed_by} />
        ),
      },
      {
        header: "Admin",
        render: (user) =>
          user.is_admin ? (
            <span
              aria-label="Administrator"
              title="Administrator"
              className="text-btn-primary dark:text-btn-primary-dark"
            >
              <FontAwesomeIcon icon={faCheck} className="text-xs" />
            </span>
          ) : null,
      },
      {
        header: "Permissions",
        render: (user) => renderPermissionsButton(user.username),
        className: "flex-shrink-0",
      },
      {
        header: "Actions",
        render: (user) => (
          <div className="invisible group-hover:visible flex space-x-2">
            <IconButton
              icon={faDesktop}
              title="Sessions"
              onClick={() => setSessionsUser(user.username)}
            />
            {user.active ? (
              <IconButton
                icon={faUserSlash}
                title="Deactivate user"
                onClick={() => setDeactivatingUser(user)}
              />
            ) : (
              <IconButton
                icon={faUserCheck}
                title="Reactivate user"
                onClick={() => setReactivatingUser(user)}
              />
            )}
          </div>
        ),
        className: "flex-shrink-0",
      },
    ],
    [],
  );

  return (
    <PageContainer title="Users">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading users list..."
        error={error}
        onRetry={refresh}
      />

      {!isLoading && !error && (
        <>
          <div className="mb-2 flex items-center gap-6">
            <SearchInput
              value={searchTerm}
              onInputChange={handleInputChange}
              onSubmit={handleSearchSubmit}
              onClear={handleClearSearch}
              placeholder="Search users..."
            />
            <Switch
              checked={showInactive}
              onChange={setShowInactive}
              label="Show inactive"
            />
          </div>

          <EntityListTable
            data={tableData}
            searchTerm={submittedTerm}
            columns={columns}
          />

          <DeactivateUserModal
            isOpen={!!deactivatingUser}
            onClose={() => setDeactivatingUser(null)}
            onConfirm={(adminOverride) => {
              void handleConfirmDeactivate(adminOverride);
            }}
            user={deactivatingUser}
            isProcessing={isDeactivating}
          />

          <DeactivateUserModal
            isOpen={!!reactivatingUser}
            onClose={() => setReactivatingUser(null)}
            onConfirm={(adminOverride) => {
              void handleConfirmReactivate(adminOverride);
            }}
            user={reactivatingUser}
            isProcessing={isReactivating}
            targetActive
          />

          <UserSessionsModal
            username={sessionsUser}
            onClose={() => setSessionsUser(null)}
          />
        </>
      )}
    </PageContainer>
  );
}

export default function UsersPage() {
  const { currentUser } = useUser();
  const isAdmin = currentUser?.is_admin ?? false;

  return isAdmin ? <AdminUsersView /> : <LegacyUsersView />;
}
