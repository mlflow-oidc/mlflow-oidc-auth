import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { useUser } from "../../core/hooks/use-user";
import { UserDetailsCard } from "./components/user-details-card";

export const UserPage = () => {
  const { currentUser, isLoading, error } = useUser();

  return (
    <PageContainer title="User Information">
      <PageStatus
        isLoading={isLoading}
        loadingText="Loading user information..."
        error={error}
      />

      {!isLoading && !error && currentUser && (
        <UserDetailsCard currentUser={currentUser} />
      )}

      {!isLoading && !error && !currentUser && (
        <p className="text-center p-8 text-lg font-medium text-text-primary dark:text-text-primary-dark">
          User is not logged in or no data was returned.
        </p>
      )}
    </PageContainer>
  );
};

export default UserPage;
