export type ManagedByBucket = "manual" | "scim" | "oidc";

/**
 * Parses the backend's `managed_by` value into a display label and a
 * classification bucket. `managed_by` is one of `"manual"`, `"scim"`, or
 * `"oidc:<provider_id>"`.
 */
export function describeManagedBy(managedBy: string): {
  label: string;
  bucket: ManagedByBucket;
} {
  if (managedBy === "scim") {
    return { label: "SCIM", bucket: "scim" };
  }
  if (managedBy.startsWith("oidc:")) {
    const providerId = managedBy.slice("oidc:".length);
    return {
      label: providerId ? `OIDC · ${providerId}` : "OIDC",
      bucket: "oidc",
    };
  }
  return { label: "Manual", bucket: "manual" };
}
