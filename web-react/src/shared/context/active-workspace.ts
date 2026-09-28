// Module-level state for http.ts integration (non-React consumers). Kept in
// its own module (rather than alongside WorkspaceProvider) so this file only
// exports plain functions, and workspace-context.tsx only exports the
// component — react-refresh needs that split to fast-refresh either file.
let _activeWorkspace: string | null = null;

export function getActiveWorkspace(): string | null {
  return _activeWorkspace;
}

export function setActiveWorkspace(workspace: string | null): void {
  _activeWorkspace = workspace;
}
