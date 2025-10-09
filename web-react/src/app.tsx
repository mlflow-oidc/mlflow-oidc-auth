import React from "react";
import { Routes, Route, Navigate } from "react-router";

const AuthPage = React.lazy(() => import("./features/auth/auth-page"));
const UserPage = React.lazy(() => import("./features/user/user-page"));
const ManagePage = React.lazy(() => import("./features/manage/manage-page"));

export default function App() {
  return (
    <Routes>
      <Route path="/auth" element={<AuthPage />} />
      <Route path="/user" element={<UserPage />} />
      <Route path="/manage" element={<ManagePage />} />

      <Route path="*" element={<Navigate to="/user" replace />} />
    </Routes>
  );
}
