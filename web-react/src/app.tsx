import React from "react";
import { Routes, Route } from "react-router";
import ProtectedRoute from "./features/auth/components/protected-route";
import RedirectIfAuth from "./features/auth/components/redirect-if-auth";
import { LoadingSpinner } from "./shared/components/loading-spinner";
import MainLayout from "./core/components/main-layout";
import ForbiddenPage from "./features/forbidden/forbidden-page";

const AuthPage = React.lazy(() => import("./features/auth/auth-page"));
const ExperimentsPage = React.lazy(
  () => import("./features/experiments/experiments-page")
);
const ExperimentPermissionsPage = React.lazy(
  () => import("./features/experiments/experiment-permissions-page")
);
const GroupsPage = React.lazy(() => import("./features/groups/groups-page"));
const ModelsPage = React.lazy(() => import("./features/models/models-page"));
const PromptsPage = React.lazy(() => import("./features/prompts/prompts-page"));
const ServiceAccountsPage = React.lazy(
  () => import("./features/service-accounts/service-accounts-page")
);
const TrashPage = React.lazy(() => import("./features/trash/trash-page"));
const UserPage = React.lazy(() => import("./features/user/user-page"));
const UsersPage = React.lazy(() => import("./features/users/users-page"));
const WebhooksPage = React.lazy(
  () => import("./features/webhooks/webhooks-page")
);
const NotFoundPage = React.lazy(
  () => import("./features/not-found/not-found-page")
);

const ProtectedLayoutRoute = ({
  children,
  isAdminRequired = false,
}: {
  children: React.ReactNode;
  isAdminRequired?: boolean;
}) => (
  <ProtectedRoute isAdminRequired={isAdminRequired}>
    <MainLayout>{children}</MainLayout>
  </ProtectedRoute>
);

export default function App() {
  return (
    <Routes>
      <Route
        path="/auth"
        element={
          <RedirectIfAuth fallback={<LoadingSpinner />}>
            <AuthPage />
          </RedirectIfAuth>
        }
      />
      <Route
        path="/experiments/"
        element={
          <ProtectedLayoutRoute>
            <ExperimentsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/experiments/:experimentId/"
        element={
          <ProtectedLayoutRoute>
            <ExperimentPermissionsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/groups/"
        element={
          <ProtectedLayoutRoute>
            <GroupsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/models/"
        element={
          <ProtectedLayoutRoute>
            <ModelsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/prompts/"
        element={
          <ProtectedLayoutRoute>
            <PromptsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/service-accounts/"
        element={
          <ProtectedLayoutRoute>
            <ServiceAccountsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/trash/"
        element={
          <ProtectedLayoutRoute isAdminRequired={true}>
            <TrashPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/user/"
        element={
          <ProtectedLayoutRoute>
            <UserPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/users/"
        element={
          <ProtectedLayoutRoute>
            <UsersPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/webhooks/"
        element={
          <ProtectedLayoutRoute isAdminRequired={true}>
            <WebhooksPage />
          </ProtectedLayoutRoute>
        }
      />

      <Route path="/403" element={<ForbiddenPage />} />
      <Route
        path="*"
        element={
          <ProtectedLayoutRoute>
            <NotFoundPage />
          </ProtectedLayoutRoute>
        }
      />
    </Routes>
  );
}
