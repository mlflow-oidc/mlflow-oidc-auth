import React from "react";
import { Navigate } from "react-router";
import { useAuth } from "../hooks/use-auth";

type Props = {
  children: React.ReactNode;
  fallback?: React.ReactNode;
};

export default function ProtectedRoute({ children }: Props) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/auth" replace />;
  }
  return <>{children}</>;
}
