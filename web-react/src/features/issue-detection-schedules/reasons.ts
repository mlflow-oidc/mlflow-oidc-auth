/** Why the guard paused (or would pause) a schedule, in words. */
export const REASON_LABELS: Record<string, string> = {
  unknown_author: "No recorded writer",
  model_changed: "Model changed since it was written",
  author_deleted: "Writer was deleted",
  author_deactivated: "Writer is deactivated",
  author_cannot_update_experiment: "Writer can no longer edit the experiment",
  author_cannot_use_model: "Writer can no longer use the endpoint or key",
  server_credentials_admin_only:
    "Runs on server credentials, which only admins may use",
  check_failed: "Could not be checked just now (retried next pass)",
};

export const reasonLabel = (reason: string | null | undefined) =>
  reason ? (REASON_LABELS[reason] ?? reason) : "";
