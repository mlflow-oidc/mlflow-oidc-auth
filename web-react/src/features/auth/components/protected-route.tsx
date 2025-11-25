import { Navigate } from "react-router";
import { useAuth } from "../hooks/use-auth";
import { useUser } from "../../../shared/context/use-user";
import { LoadingSpinner } from "../../../shared/components/loading-spinner";

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

  if (isLoading || !currentUser) return <LoadingSpinner />;

  if (error) {
    return <div>Error loading user: {error.message}</div>;
  }

  if (isAdminRequired && !currentUser.is_admin) {
    return <Navigate to="/403" replace />;
  }

  return <>{children}</>;
}
