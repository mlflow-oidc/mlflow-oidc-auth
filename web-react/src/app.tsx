import React from "react";
import { Routes, Route } from "react-router";
import ProtectedRoute from "./features/auth/components/protected-route";
import RedirectIfAuth from "./features/auth/components/redirect-if-auth";
import { LoadingSpinner } from "./shared/components/loading-spinner";
import MainLayout from "./core/components/main-layout";
import ForbiddenPage from "./features/forbidden/forbidden-page";

const AuthPage = React.lazy(() => import("./features/auth/auth-page"));
const AiEndpointsPage = React.lazy(
  () => import("./features/ai-gateway/ai-endpoints-page"),
);
const AiSecretsPage = React.lazy(
  () => import("./features/ai-gateway/ai-secrets-page"),
);
const AiModelsPage = React.lazy(
  () => import("./features/ai-gateway/ai-models-page"),
);
const ExperimentsPage = React.lazy(
  () => import("./features/experiments/experiments-page"),
);
const ExperimentPermissionsPage = React.lazy(
  () => import("./features/experiments/experiment-permissions-page"),
);
const GroupsPage = React.lazy(() => import("./features/groups/groups-page"));
const GroupPermissionsPage = React.lazy(
  () => import("./features/groups/group-permissions-page"),
);
const ModelsPage = React.lazy(() => import("./features/models/models-page"));
const ModelPermissionsPage = React.lazy(
  () => import("./features/models/model-permissions-page"),
);
const PromptsPage = React.lazy(() => import("./features/prompts/prompts-page"));
const PromptPermissionsPage = React.lazy(
  () => import("./features/prompts/prompt-permissions-page"),
);
const ServiceAccountsPage = React.lazy(
  () => import("./features/service-accounts/service-accounts-page"),
);
const ServiceAccountPermissionPage = React.lazy(
  () => import("./features/service-accounts/service-account-permission-page"),
);

const TrashPage = React.lazy(() => import("./features/trash/trash-page"));
const UserPage = React.lazy(() => import("./features/user/user-page"));
const UsersPage = React.lazy(() => import("./features/users/users-page"));
const UserPermissionsPage = React.lazy(
  () => import("./features/users/user-permissions-page"),
);
const WebhooksPage = React.lazy(
  () => import("./features/webhooks/webhooks-page"),
);
const NotFoundPage = React.lazy(
  () => import("./features/not-found/not-found-page"),
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
        path="/ai-gateway/endpoints"
        element={
          <ProtectedLayoutRoute>
            <AiEndpointsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/ai-gateway/secrets"
        element={
          <ProtectedLayoutRoute>
            <AiSecretsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/ai-gateway/models"
        element={
          <ProtectedLayoutRoute>
            <AiModelsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/auth"
        element={
          <RedirectIfAuth fallback={<LoadingSpinner />}>
            <AuthPage />
          </RedirectIfAuth>
        }
      />
      <Route
        path="/experiments"
        element={
          <ProtectedLayoutRoute>
            <ExperimentsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/experiments/:experimentId"
        element={
          <ProtectedLayoutRoute>
            <ExperimentPermissionsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/groups"
        element={
          <ProtectedLayoutRoute>
            <GroupsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/groups/:groupName/experiments"
        element={
          <ProtectedLayoutRoute>
            <GroupPermissionsPage type="experiments" />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/groups/:groupName/models"
        element={
          <ProtectedLayoutRoute>
            <GroupPermissionsPage type="models" />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/groups/:groupName/prompts"
        element={
          <ProtectedLayoutRoute>
            <GroupPermissionsPage type="prompts" />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/models"
        element={
          <ProtectedLayoutRoute>
            <ModelsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/models/:modelName"
        element={
          <ProtectedLayoutRoute>
            <ModelPermissionsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/prompts"
        element={
          <ProtectedLayoutRoute>
            <PromptsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/prompts/:promptName"
        element={
          <ProtectedLayoutRoute>
            <PromptPermissionsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/service-accounts"
        element={
          <ProtectedLayoutRoute>
            <ServiceAccountsPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/service-accounts/:username/experiments"
        element={
          <ProtectedLayoutRoute>
            <ServiceAccountPermissionPage type="experiments" />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/service-accounts/:username/models"
        element={
          <ProtectedLayoutRoute>
            <ServiceAccountPermissionPage type="models" />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/service-accounts/:username/prompts"
        element={
          <ProtectedLayoutRoute>
            <ServiceAccountPermissionPage type="prompts" />
          </ProtectedLayoutRoute>
        }
      />

      <Route
        path="/trash/:tab?"
        element={
          <ProtectedLayoutRoute isAdminRequired={true}>
            <TrashPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/user/:tab?"
        element={
          <ProtectedLayoutRoute>
            <UserPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/users"
        element={
          <ProtectedLayoutRoute>
            <UsersPage />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/users/:username/experiments"
        element={
          <ProtectedLayoutRoute>
            <UserPermissionsPage type="experiments" />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/users/:username/models"
        element={
          <ProtectedLayoutRoute>
            <UserPermissionsPage type="models" />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/users/:username/prompts"
        element={
          <ProtectedLayoutRoute>
            <UserPermissionsPage type="prompts" />
          </ProtectedLayoutRoute>
        }
      />
      <Route
        path="/webhooks"
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
