import React from "react";
import { Navigate, useLocation } from "react-router";
import { useAuth } from "./use-auth";

type AuthShape = {
  status?: "loading" | "unauthenticated" | "authenticated";
  authenticated?: boolean;
  user?: unknown;
  permissions?: string[];
};

type ProtectedRouteProps = {
  children: React.ReactElement;
  fallback?: React.ReactNode;
};

export default function ProtectedRoute({
  children,
  fallback = null,
}: ProtectedRouteProps) {
  const auth = useAuth() as AuthShape;
  const location = useLocation();

  // Normalize auth shape your hook may produce. Prefer explicit status when available.
  const status =
    auth.status ??
    (typeof auth.authenticated === "boolean"
      ? auth.authenticated
        ? "authenticated"
        : "unauthenticated"
      : "loading");

  if (status === "loading") return <>{fallback}</>;

  if (status !== "authenticated") {
    // Not logged in — remember where we wanted to go
    return <Navigate to="/auth" replace state={{ from: location }} />;
  }

  return children;
}
