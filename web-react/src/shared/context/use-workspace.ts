import { createContext, use } from "react";

export type WorkspaceContextValue = {
  selectedWorkspace: string | null; // null means "All Workspaces"
  setSelectedWorkspace: (workspace: string | null) => void;
};

export const WorkspaceContext = createContext<WorkspaceContextValue | null>(
  null,
);

export function useWorkspace(): WorkspaceContextValue {
  const ctx = use(WorkspaceContext);
  if (!ctx) {
    throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  }
  return ctx;
}
