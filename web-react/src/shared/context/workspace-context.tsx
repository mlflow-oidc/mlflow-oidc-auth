import { useState, useEffect, type ReactNode } from "react";
import { WorkspaceContext } from "./use-workspace";

const STORAGE_KEY = "mlflow-oidc-workspace";

// Module-level state for http.ts integration (non-React consumers)
let _activeWorkspace: string | null = null;

export function getActiveWorkspace(): string | null {
  return _activeWorkspace;
}

export function setActiveWorkspace(workspace: string | null): void {
  _activeWorkspace = workspace;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [selectedWorkspace, setSelectedWorkspaceState] = useState<
    string | null
  >(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      // Eagerly sync to module-level state so that any http() call
      // during the first render cycle already has the right workspace.
      setActiveWorkspace(stored);
      return stored;
    } catch {
      return null;
    }
  });

  const setSelectedWorkspace = (workspace: string | null) => {
    // Update module-level state synchronously so that child effects
    // (e.g. useApi re-fetch) read the new workspace when they call
    // getActiveWorkspace() via http(). React runs child effects before
    // parent effects, so deferring this to a useEffect would cause
    // stale reads.
    setActiveWorkspace(workspace);
    setSelectedWorkspaceState(workspace);
  };

  // Sync to localStorage (module-level state is already set synchronously
  // in setSelectedWorkspace above and in the initializer effect below)
  useEffect(() => {
    try {
      if (selectedWorkspace === null) {
        localStorage.removeItem(STORAGE_KEY);
      } else {
        localStorage.setItem(STORAGE_KEY, selectedWorkspace);
      }
    } catch {
      // Ignore storage errors (private browsing, etc.)
    }
  }, [selectedWorkspace]);

  // Initialize module-level state on mount (covers page reload where
  // setSelectedWorkspace is not called but localStorage has a value)
  useEffect(() => {
    setActiveWorkspace(selectedWorkspace);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <WorkspaceContext value={{ selectedWorkspace, setSelectedWorkspace }}>
      {children}
    </WorkspaceContext>
  );
}
