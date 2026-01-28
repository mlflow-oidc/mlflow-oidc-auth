import { describe, it, expect } from "vitest";
import { removeTrailingSlashes } from "./string-utils";

describe("removeTrailingSlashes", () => {
  const cases: Array<[string | undefined | null, string]> = [
    [undefined, ""],
    [null, ""],
    ["", ""],
    ["/", ""],
    ["///", ""],
    ["//", ""],
    ["/path/", "/path"],
    ["/path///", "/path"],
    ["no/trailing", "no/trailing"],
    ["path/with/many////", "path/with/many"],
    ["/a/b/c/", "/a/b/c"],
    ["///a///", "///a"],
  ];

  for (const [input, expected] of cases) {
    it(`should convert ${String(input)} -> ${expected}`, () => {
      expect(removeTrailingSlashes(input)).toBe(expected);
    });
  }
});
