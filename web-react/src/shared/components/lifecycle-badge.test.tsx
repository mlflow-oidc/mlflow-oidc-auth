import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { LifecycleBadge } from "./lifecycle-badge";

describe("LifecycleBadge", () => {
  it("renders Active for an active state", () => {
    render(<LifecycleBadge variant="state" active={true} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders Inactive for an inactive state", () => {
    render(<LifecycleBadge variant="state" active={false} />);
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("renders Manual for managed_by 'manual'", () => {
    render(<LifecycleBadge variant="managed_by" managedBy="manual" />);
    expect(screen.getByText("Manual")).toBeInTheDocument();
  });

  it("renders SCIM for managed_by 'scim'", () => {
    render(<LifecycleBadge variant="managed_by" managedBy="scim" />);
    expect(screen.getByText("SCIM")).toBeInTheDocument();
  });

  it("renders 'OIDC · <provider>' for managed_by 'oidc:<provider>'", () => {
    render(
      <LifecycleBadge variant="managed_by" managedBy="oidc:okta-prod" />,
    );
    expect(screen.getByText("OIDC · okta-prod")).toBeInTheDocument();
  });

  it("falls back to a bare OIDC label with no provider id", () => {
    render(<LifecycleBadge variant="managed_by" managedBy="oidc:" />);
    expect(screen.getByText("OIDC")).toBeInTheDocument();
  });
});
