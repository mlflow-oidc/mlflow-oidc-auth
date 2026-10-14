import { describe, it, expect } from "vitest";
import { isPermissionLevel, withPermissionLevels } from "./permission-level";

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
  it("keeps every field of a row whose permission is a level", () => {
    const rows = [{ workspace: "ws", group_name: "g", permission: "EDIT", rule_id: 3 }];
    expect(withPermissionLevels(rows, "test")).toEqual(rows);
  });

  it("throws on a permission that is not a level, naming it", () => {
    expect(() =>
      withPermissionLevels(
        [{ workspace: "ws", username: "u", permission: "OWNER" }],
        "GET /users",
      ),
    ).toThrow('Unexpected permission "OWNER" in the response of GET /users');
  });
});
