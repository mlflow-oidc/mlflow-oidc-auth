const DNS_SAFE_PATTERN = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/;
const RESERVED_NAMES = ["default"];

export function validateWorkspaceName(name: string): string | null {
  if (!name) return "Workspace name is required";
  if (name.length < 2) return "Name must be at least 2 characters";
  if (name.length > 63) return "Name must be at most 63 characters";
  if (!DNS_SAFE_PATTERN.test(name))
    return "Name must be DNS-safe: lowercase letters, digits, hyphens; must start and end with alphanumeric";
  if (RESERVED_NAMES.includes(name)) return "This name is reserved";
  return null;
}
