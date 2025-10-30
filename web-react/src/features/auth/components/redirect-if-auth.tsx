import React from "react";
import { Navigate } from "react-router";
import { useAuth } from "../hooks/use-auth";

type Props = {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  to?: string; // default /user
};

export default function RedirectIfAuth({ children, to = "/user" }: Props) {
  const { isAuthenticated } = useAuth();
  if (isAuthenticated) {
    return <Navigate to={to} replace />;
  }

  return <>{children}</>;
}
