import React from "react";
import { Navigate, useLocation } from "react-router";
import { useAuth } from "./use-auth";

type AuthShape = {
  status?: "loading" | "unauthenticated" | "authenticated";
  authenticated?: boolean;
};

type LocationState = {
  from?: { pathname?: string };
} | null;

type RedirectIfAuthProps = {
  children: React.ReactElement;
  fallback?: React.ReactNode;
};

export default function RedirectIfAuth({
  children,
  fallback = null,
}: RedirectIfAuthProps) {
  const auth = useAuth() as AuthShape;
  const location = useLocation();

  const state = (location.state as LocationState) ?? null;
  const status =
    auth.status ??
    (typeof auth.authenticated === "boolean"
      ? auth.authenticated
        ? "authenticated"
        : "unauthenticated"
      : "loading");

  if (status === "loading") return <>{fallback}</>;

  if (status === "authenticated") {
    // If user arrived at /auth but is already authenticated, redirect them back or to /user
    const from = state?.from?.pathname ?? "/user";
    return <Navigate to={from} replace />;
  }

  return children;
}
