import { Navigate } from "react-router";
import { useAuth } from "../../../core/hooks/use-auth";
import { useUser } from "../../../core/hooks/use-user";
import { LoadingSpinner } from "../../../shared/components/loading-spinner";
import { Button } from "../../../shared/components/button";

type Props = {
  children: React.ReactNode;
  isAdminRequired?: boolean;
};

export default function ProtectedRoute({
  children,
  isAdminRequired = false,
}: Props) {
  const { isAuthenticated } = useAuth();
  const { currentUser, isLoading, error } = useUser();

  if (!isAuthenticated) return <Navigate to="/auth" replace />;

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen p-4 text-center">
        <h2 className="text-xl font-bold text-status-danger dark:text-status-danger-dark mb-2">Error Loading User</h2>
        <p className="text-status-danger dark:text-status-danger-dark mb-4 opacity-90">{error.message}</p>
        <Button
          variant="danger"
          onClick={() => window.location.reload()}
        >
          Try Again
        </Button>
      </div>
    );
  }

  if (isLoading && !currentUser) return <LoadingSpinner />;

  if (!currentUser) return <LoadingSpinner />;

  if (isAdminRequired && !currentUser.is_admin) {
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}
