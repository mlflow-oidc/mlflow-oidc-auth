import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useLocation } from "react-router";
import { fetchAuthStatus } from "../services/auth-service";

type Props = {
  children: React.ReactNode;
  fallback?: React.ReactNode;
};

export default function ProtectedRoute({ children, fallback }: Props) {
  const location = useLocation();
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const key = useMemo(() => location.pathname, [location.pathname]);

  useEffect(() => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    let active = true;
    setLoading(true);

    fetchAuthStatus(ac.signal)
      .then(({ authenticated }) => {
        if (!active) return;
        setAuthenticated(authenticated);
      })
      .catch(() => {
        if (!active) return;
        setAuthenticated(false);
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
      });

    return () => {
      active = false;
      ac.abort();
    };
  }, [key]);

  if (loading) return <>{fallback ?? <div>Loading...</div>}</>;
  if (!authenticated) return <Navigate to="/auth" replace />;
  return <>{children}</>;
}
