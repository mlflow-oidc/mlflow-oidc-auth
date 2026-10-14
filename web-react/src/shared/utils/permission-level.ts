import type { PermissionLevel } from "../types/entity";

// A record rather than an array so the compiler insists every PermissionLevel is listed.
const PERMISSION_LEVELS: Record<PermissionLevel, true> = {
  READ: true,
  USE: true,
  EDIT: true,
  MANAGE: true,
  NO_PERMISSIONS: true,
};

/** Whether `value` is one of the permission levels the server grants. */
export function isPermissionLevel(value: string): value is PermissionLevel {
  return Object.prototype.hasOwnProperty.call(PERMISSION_LEVELS, value);
}

/**
 * Narrow the `permission` of each row the API returned to a {@link PermissionLevel}.
 *
 * The API contract types `permission` as a plain string. The server only ever stores a level
 * there; a value that is not one is a server bug, and is reported rather than shown as something
 * it is not.
 *
 * @throws Error naming the unexpected value and where it came from.
 */
export function withPermissionLevels<T extends { permission: string }>(
  rows: T[],
  source: string,
): (Omit<T, "permission"> & { permission: PermissionLevel })[] {
  return rows.map((row) => {
    const { permission } = row;
    if (!isPermissionLevel(permission)) {
      throw new Error(
        `Unexpected permission "${permission}" in the response of ${source}`,
      );
    }
    return { ...row, permission };
  });
}
