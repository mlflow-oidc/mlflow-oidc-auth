import Header from "../../shared/components/header";
import { useCurrentUser } from "../../features/auth/hooks/use-current-user";

export const UserPage = () => {
  const { currentUser, loading, error } = useCurrentUser();

  const userName =
    currentUser?.display_name || currentUser?.username || "Guest";

  return (
    <>
      <Header userName={userName} />
      <div
        className="
          p-8 shadow-md min-h-screen
          bg-ui-bg text-ui-text
          dark:bg-ui-bg-dark dark:text-ui-text-dark
        "
      >
        <div className="p-6 mt-12 border border-gray-300 dark:border-gray-700 rounded-lg">
          <h2 className="text-2xl font-bold mb-4 text-center">
            User Information
          </h2>

          {loading && (
            <p className="text-center">Loading user information...</p>
          )}

          {error && (
            <p className="text-red-500 text-center">
              Error loading user information: {error.message}
            </p>
          )}

          {!loading && !error && (
            <div className="text-left max-w-lg mx-auto p-4 bg-ui-control-bg dark:bg-ui-control-bg-dark rounded-md">
              {currentUser ? (
                <ul className="space-y-2">
                  <li className="flex justify-between border-b dark:border-gray-700 pb-1">
                    <strong className="font-semibold">Display Name:</strong>
                    <span>{currentUser.display_name}</span>
                  </li>
                  <li className="flex justify-between border-b dark:border-gray-700 pb-1">
                    <strong className="font-semibold">Username:</strong>
                    <span>{currentUser.username}</span>
                  </li>
                  <li className="flex justify-between border-b dark:border-gray-700 pb-1">
                    <strong className="font-semibold">User ID:</strong>
                    <span>{currentUser.id}</span>
                  </li>
                  <li className="flex justify-between border-b dark:border-gray-700 pb-1">
                    <strong className="font-semibold">Is Admin:</strong>
                    <span>{currentUser.is_admin ? "Yes" : "No"}</span>
                  </li>
                  <li className="flex justify-between pb-1">
                    <strong className="font-semibold">Service Account:</strong>
                    <span>{currentUser.is_service_account ? "Yes" : "No"}</span>
                  </li>
                  <li className="pt-2">
                    <strong className="font-semibold block mb-1">
                      Groups:
                    </strong>
                    <ul className="list-disc list-inside ml-4 text-sm">
                      {currentUser.groups.map((group) => (
                        <li key={group.id}>{group.group_name}</li>
                      ))}
                    </ul>
                  </li>

                  <li className="text-xs pt-2 text-gray-500 dark:text-gray-400">
                    {currentUser.password_expiration == null
                      ? "You have no access token yet"
                      : `Your token expires on: ${currentUser.password_expiration}`}
                  </li>
                </ul>
              ) : (
                <p className="text-center">
                  User is not logged in or no data was returned.
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default UserPage;
