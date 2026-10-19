import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { MockInstance } from "vitest";
import {
  _resetPermissionWarningsForTests,
  isPermissionLevel,
  withPermissionLevels,
} from "./permission-level";

describe("isPermissionLevel", () => {
  it.each(["READ", "USE", "EDIT", "MANAGE", "NO_PERMISSIONS"])(
    "accepts %s",
    (level) => {
      expect(isPermissionLevel(level)).toBe(true);
    },
  );

  it.each(["read", "ADMIN", "", "toString", "__proto__"])(
    "rejects %j",
    (value) => {
      expect(isPermissionLevel(value)).toBe(false);
    },
  );
});

describe("withPermissionLevels", () => {
  let warn: MockInstance<typeof console.warn>;

  beforeEach(() => {
    _resetPermissionWarningsForTests();
    warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
  });

  afterEach(() => {
    warn.mockRestore();
  });

  it("keeps every field of a row whose permission is a level, without warning", () => {
    const rows = [
      { workspace: "ws", group_name: "g", permission: "EDIT", rule_id: 3 },
    ];
    expect(withPermissionLevels(rows, "test")).toEqual(rows);
    expect(warn).not.toHaveBeenCalled();
  });

  it("keeps a row with an unrecognized permission, raw value intact", () => {
    const rows = [
      { workspace: "ws", username: "a", permission: "READ" },
      { workspace: "ws", username: "b", permission: "OWNER" },
    ];
    const result = withPermissionLevels(rows, "GET /users");
    expect(result).toEqual(rows);
    expect(result[1].permission).toBe("OWNER");
  });

  it("warns once per unrecognized value", () => {
    const rows = [
      { workspace: "ws", username: "a", permission: "OWNER" },
      { workspace: "ws", username: "b", permission: "OWNER" },
    ];
    withPermissionLevels(rows, "GET /users");
    withPermissionLevels(rows, "GET /users");
    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledWith(
      'Unrecognized permission "OWNER" in the response of GET /users; showing it as is.',
    );
  });
});
