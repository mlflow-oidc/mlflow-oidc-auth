import Header from "../../shared/components/header";
import { useCurrentUser } from "../../features/auth/hooks/use-current-user";
import { UserDetailsCard } from "./components/user-details-card";

export const UserPage = () => {
  const { currentUser, loading, error } = useCurrentUser();

  const userName =
    currentUser?.display_name || currentUser?.username || "Guest";

  return (
    <div className="min-h-screen bg-ui-bg text-ui-text dark:bg-ui-bg-dark dark:text-ui-text-dark">
      <Header userName={userName} />
      <div className="p-4 md:p-6 mx-auto md:mt-12">
        <h2 className="text-3xl font-semibold mb-6 text-center">
          User Information
        </h2>

        {loading && (
          <div className="text-center p-8">
            <p className="text-lg font-medium animate-pulse">
              Loading user information...
            </p>
          </div>
        )}

        {error && (
          <div className="text-center p-8 border border-red-400 bg-red-50 dark:bg-red-900 rounded-lg">
            <p className="text-red-600 dark:text-red-300 font-semibold">
              Error loading user information: {error.message}
            </p>
          </div>
        )}

        {!loading && !error && currentUser && (
          <UserDetailsCard currentUser={currentUser} />
        )}

        {!loading && !error && !currentUser && (
          <p className="text-center p-8 text-lg font-medium text-gray-600 dark:text-gray-400">
            User is not logged in or no data was returned.
          </p>
        )}
      </div>
    </div>
  );
};

export default UserPage;
