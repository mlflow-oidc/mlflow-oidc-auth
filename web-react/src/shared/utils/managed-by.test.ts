import { describe, it, expect } from "vitest";
import { describeManagedBy, isDirectoryManaged } from "./managed-by";

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

  it("classifies saml:<provider>", () => {
    expect(describeManagedBy("saml:corp-idp")).toEqual({
      label: "SAML · corp-idp",
      bucket: "saml",
    });
  });

  it("falls back to a bare SAML label with no provider id", () => {
    expect(describeManagedBy("saml:")).toEqual({
      label: "SAML",
      bucket: "saml",
    });
  });
});

describe("isDirectoryManaged", () => {
  it("is true for scim", () => {
    expect(isDirectoryManaged("scim")).toBe(true);
  });

  it("is true for oidc:<provider>", () => {
    expect(isDirectoryManaged("oidc:google")).toBe(true);
  });

  it("is true for saml:<provider>", () => {
    expect(isDirectoryManaged("saml:corp-idp")).toBe(true);
  });

  it("is false for manual", () => {
    expect(isDirectoryManaged("manual")).toBe(false);
  });
});
