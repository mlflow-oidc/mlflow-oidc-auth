import { describe, it, expect } from "vitest";
import { describeManagedBy } from "./managed-by";

describe("describeManagedBy", () => {
  it("classifies manual", () => {
    expect(describeManagedBy("manual")).toEqual({
      label: "Manual",
      bucket: "manual",
    });
  });

  it("classifies scim", () => {
    expect(describeManagedBy("scim")).toEqual({
      label: "SCIM",
      bucket: "scim",
    });
  });

  it("classifies oidc:<provider>", () => {
    expect(describeManagedBy("oidc:google")).toEqual({
      label: "OIDC · google",
      bucket: "oidc",
    });
  });

  it("falls back to a bare OIDC label with no provider id", () => {
    expect(describeManagedBy("oidc:")).toEqual({
      label: "OIDC",
      bucket: "oidc",
    });
  });

  it("treats any unrecognized value as manual", () => {
    expect(describeManagedBy("something-else")).toEqual({
      label: "Manual",
      bucket: "manual",
    });
  });
});
