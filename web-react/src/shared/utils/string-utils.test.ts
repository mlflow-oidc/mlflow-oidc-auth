import { describe, it, expect } from "vitest";
import { removeTrailingSlashes, encodeRouteParam } from "./string-utils";

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

describe("encodeRouteParam", () => {
  it("encodes slashes", () => {
    expect(encodeRouteParam("model/v1")).toBe("model%2Fv1");
  });

  it("encodes percent signs", () => {
    expect(encodeRouteParam("100%_resource")).toBe("100%25_resource");
  });

  it("encodes question marks and hashes", () => {
    expect(encodeRouteParam("resource?v=1#readme")).toBe(
      "resource%3Fv=1%23readme",
    );
  });

  it("keeps '@' unencoded", () => {
    expect(encodeRouteParam("alice@example.com")).toBe("alice@example.com");
  });

  it("keeps dots, hyphens and underscores unencoded", () => {
    expect(encodeRouteParam("my-app.v1_final")).toBe("my-app.v1_final");
  });
});
