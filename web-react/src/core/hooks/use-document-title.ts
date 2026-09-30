import { useEffect } from "react";
import { useLocation } from "react-router";

export const APP_NAME = "MLflow Access Control";

const SEPARATOR = " · ";

// First path segment → section label. Detail routes add the item they show in front of it.
const SECTIONS: Record<string, string> = {
  "403": "Access denied",
  auth: "Sign in",
  experiments: "Experiments",
  groups: "Groups",
  models: "Models",
  prompts: "Prompts",
  scim: "SCIM",
  "service-accounts": "Service accounts",
  trash: "Trash",
  user: "My account",
  users: "Users",
  webhooks: "Webhooks",
  workspaces: "Workspaces",
  "workspace-rules": "Workspace rules",
};

// /ai-gateway/<kind>/... is a section per kind.
const AI_GATEWAY_SECTIONS: Record<string, string> = {
  "ai-endpoints": "AI endpoints",
  models: "AI models",
  secrets: "AI secrets",
};

// Sections whose second segment is a tab or view, not the item being shown.
const TABBED_SECTIONS = new Set(["trash", "user"]);

// Permission tabs of a user, group or service account (/users/<name>/<tab>).
const PERMISSION_TABS: Record<string, string> = {
  experiments: "Experiments",
  models: "Models",
  prompts: "Prompts",
  "ai-endpoints": "AI endpoints",
  "ai-secrets": "AI secrets",
  "ai-models": "AI models",
};

function decodeSegment(segment: string): string {
  try {
    return decodeURIComponent(segment);
  } catch {
    return segment;
  }
}

/**
 * Title for the page at ``pathname`` (relative to the router basename):
 * "<item> · <tab> · <section> · MLflow Access Control" on a permission tab,
 * "<item> · <section> · MLflow Access Control" on a detail page,
 * "<section> · MLflow Access Control" on a list page, and "Not found · …" for any
 * route the app has no page for (including "/", which renders the not-found page).
 */
export function pageTitleFor(pathname: string): string {
  const segments = pathname.split("/").filter(Boolean);

  let section: string | undefined;
  let item: string | undefined;
  let tab: string | undefined;
  if (segments[0] === "ai-gateway") {
    section = AI_GATEWAY_SECTIONS[segments[1] ?? ""];
    item = segments[2];
  } else {
    section = SECTIONS[segments[0] ?? ""];
    item = TABBED_SECTIONS.has(segments[0]) ? undefined : segments[1];
    tab = PERMISSION_TABS[segments[2] ?? ""];
  }

  if (!section) {
    return ["Not found", APP_NAME].join(SEPARATOR);
  }
  return [item ? decodeSegment(item) : undefined, tab, section, APP_NAME]
    .filter(Boolean)
    .join(SEPARATOR);
}

/** Keep ``document.title`` in step with the current route. */
export function useDocumentTitle(): void {
  const { pathname } = useLocation();
  useEffect(() => {
    document.title = pageTitleFor(pathname);
  }, [pathname]);
}
