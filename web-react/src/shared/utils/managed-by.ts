export type ManagedByBucket = "manual" | "scim" | "oidc" | "saml";

/**
 * Parses the backend's `managed_by` value into a display label and a
 * classification bucket. `managed_by` is one of `"manual"`, `"scim"`,
 * `"oidc:<provider_id>"`, or `"saml:<provider_id>"` (see
 * `LOGIN_SOURCE_PREFIXES` in `mlflow_oidc_auth/ownership.py`).
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
  if (managedBy.startsWith("saml:")) {
    const providerId = managedBy.slice("saml:".length);
    return {
      label: providerId ? `SAML · ${providerId}` : "SAML",
      bucket: "saml",
    };
  }
  return { label: "Manual", bucket: "manual" };
}

/**
 * Whether an identity provider (SCIM or a login source) owns this account,
 * meaning a future sync could overwrite a manual change unless it is made
 * with the ownership override.
 */
export function isDirectoryManaged(managedBy: string): boolean {
  const { bucket } = describeManagedBy(managedBy);
  return bucket === "scim" || bucket === "oidc" || bucket === "saml";
}
