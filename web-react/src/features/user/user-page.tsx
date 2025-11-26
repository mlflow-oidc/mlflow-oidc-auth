import { useUser } from "../../core/hooks/use-user";
import { UserDetailsCard } from "./components/user-details-card";

export const UserPage = () => {
  const { currentUser, isLoading, error } = useUser();

  return (
    <>
      <h2 className="text-3xl font-semibold mb-4 text-center text-ui-text dark:text-ui-text-dark">
        User Information
      </h2>

      {isLoading && (
        <div className="text-center p-8">
          <p className="text-lg font-medium animate-pulse text-text-primary dark:text-text-primary-dark">
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

      {!isLoading && !error && currentUser && (
        <UserDetailsCard currentUser={currentUser} />
      )}

      {!isLoading && !error && !currentUser && (
        <p className="text-center p-8 text-lg font-medium text-text-primary dark:text-text-primary-dark">
          User is not logged in or no data was returned.
        </p>
      )}
    </>
  );
};

export default UserPage;
