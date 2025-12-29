import PageContainer from "../../shared/components/page/page-container";
import PageStatus from "../../shared/components/page/page-status";
import { useUser } from "../../core/hooks/use-user";
import { UserDetailsCard } from "./components/user-details-card";

export const UserPage = () => {
  const { currentUser, isLoading, error } = useUser();

  return (
    <PageContainer title="User Information">
      <PageStatus
        isLoading={isLoading && !currentUser}
        loadingText="Loading user information..."
        error={error}
      />

      {(currentUser || (!isLoading && !error)) && currentUser && (
        <UserDetailsCard currentUser={currentUser} />
      )}
    </PageContainer>
  );
};

export default UserPage;
