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
      return localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  });

  const setSelectedWorkspace = (workspace: string | null) => {
    setSelectedWorkspaceState(workspace);
  };

  // Sync to localStorage and module-level state
  useEffect(() => {
    setActiveWorkspace(selectedWorkspace);
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

  // Initialize module-level state on mount
  useEffect(() => {
    setActiveWorkspace(selectedWorkspace);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <WorkspaceContext value={{ selectedWorkspace, setSelectedWorkspace }}>
      {children}
    </WorkspaceContext>
  );
}
