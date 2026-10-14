import type {
  GrantedPermission,
  PermissionLevel,
  UnrecognizedPermission,
} from "../types/entity";

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

const warned = new Set<string>();

/** Reset the once-per-value warning memory — exposed for tests. */
export function _resetPermissionWarningsForTests(): void {
  warned.clear();
}

/**
 * Narrow the `permission` of each row the API returned to a {@link GrantedPermission}.
 *
 * The API contract types `permission` as a plain string. The server only ever stores a level
 * there, but one unexpected value must not take the page down with it: the row is kept, its raw
 * value becomes an {@link UnrecognizedPermission} the UI shows as is, and the value is reported
 * with `console.warn` once.
 */
export function withPermissionLevels<T extends { permission: string }>(
  rows: T[],
  source: string,
): (Omit<T, "permission"> & { permission: GrantedPermission })[] {
  return rows.map((row) => {
    const { permission } = row;
    if (isPermissionLevel(permission)) {
      return { ...row, permission };
    }
    if (!warned.has(permission)) {
      warned.add(permission);
      console.warn(
        `Unrecognized permission "${permission}" in the response of ${source}; showing it as is.`,
      );
    }
    return { ...row, permission: permission as UnrecognizedPermission };
  });
}
