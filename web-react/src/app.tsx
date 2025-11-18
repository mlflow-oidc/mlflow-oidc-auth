import React from "react";
import { Routes, Route, Navigate } from "react-router";
import ProtectedRoute from "./features/auth/components/protected-route";
import RedirectIfAuth from "./features/auth/components/redirect-if-auth";
import { LoadingSpinner } from "./shared/components/loading-spinner";
import MainLayout from "./shared/components/main-layout";

const AuthPage = React.lazy(() => import("./features/auth/auth-page"));
const UserPage = React.lazy(() => import("./features/user/user-page"));
const ManagePage = React.lazy(() => import("./features/manage/manage-page"));

const ProtectedLayoutRoute = ({ children }: { children: React.ReactNode }) => (
  <ProtectedRoute>
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
        path="/user/*"
        element={
          <ProtectedLayoutRoute>
            <UserPage />
          </ProtectedLayoutRoute>
        }
      />

      <Route
        path="/manage/*"
        element={
          <ProtectedLayoutRoute>
            <ManagePage />
          </ProtectedLayoutRoute>
        }
      />

      <Route path="/403" element={<div>Forbidden</div>} />
      <Route path="*" element={<Navigate to="/user" replace />} />
    </Routes>
  );
}
