import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DeactivateUserModal } from "./deactivate-user-modal";
import type { UserDetails } from "../../../shared/types/user";

const manualUser: UserDetails = {
  username: "alice@example.com",
  display_name: "Alice",
  is_admin: false,
  is_service_account: false,
  active: true,
  managed_by: "manual",
};

const scimUser: UserDetails = {
  ...manualUser,
  username: "bob@example.com",
  managed_by: "scim",
};

const oidcUser: UserDetails = {
  ...manualUser,
  username: "carol@example.com",
  managed_by: "oidc:okta-prod",
};

const samlUser: UserDetails = {
  ...manualUser,
  username: "dave@example.com",
  managed_by: "saml:corp-idp",
};

describe("DeactivateUserModal", () => {
  it("renders nothing when there is no target user", () => {
    const { container } = render(
      <DeactivateUserModal
        isOpen={false}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        user={null}
        isProcessing={false}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the confirmation copy for a manually managed user, no override switch", () => {
    render(
      <DeactivateUserModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        user={manualUser}
        isProcessing={false}
      />,
    );

    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(
      screen.queryByText("Override ownership guard"),
    ).not.toBeInTheDocument();
  });

  it("calls onConfirm with adminOverride=false by default", () => {
    const onConfirm = vi.fn();
    render(
      <DeactivateUserModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={onConfirm}
        user={manualUser}
        isProcessing={false}
      />,
    );

    fireEvent.click(screen.getByText("Deactivate"));
    expect(onConfirm).toHaveBeenCalledWith(false);
  });

  it("shows the ownership guard warning and override switch for a SCIM-managed user", () => {
    render(
      <DeactivateUserModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        user={scimUser}
        isProcessing={false}
      />,
    );

    expect(screen.getByText("SCIM")).toBeInTheDocument();
    expect(screen.getByText("Override ownership guard")).toBeInTheDocument();
  });

  it("shows the ownership guard warning for an OIDC-managed user", () => {
    render(
      <DeactivateUserModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        user={oidcUser}
        isProcessing={false}
      />,
    );

    expect(screen.getByText("OIDC · okta-prod")).toBeInTheDocument();
    expect(screen.getByText("Override ownership guard")).toBeInTheDocument();
  });

  it("calls onConfirm with adminOverride=true when the override switch is toggled on", () => {
    const onConfirm = vi.fn();
    render(
      <DeactivateUserModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={onConfirm}
        user={scimUser}
        isProcessing={false}
      />,
    );

    fireEvent.click(screen.getByRole("switch"));
    fireEvent.click(screen.getByText("Deactivate"));
    expect(onConfirm).toHaveBeenCalledWith(true);
  });

  it("disables the buttons while processing", () => {
    render(
      <DeactivateUserModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        user={manualUser}
        isProcessing={true}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Deactivating..." }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("shows the ownership guard warning and override switch for a SAML-managed user", () => {
    render(
      <DeactivateUserModal
        isOpen={true}
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        user={samlUser}
        isProcessing={false}
      />,
    );

    expect(screen.getByText("SAML · corp-idp")).toBeInTheDocument();
    expect(screen.getByText("Override ownership guard")).toBeInTheDocument();
  });

  describe("targetActive (reactivation)", () => {
    it("renders reactivation copy and the Reactivate action", () => {
      render(
        <DeactivateUserModal
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          user={manualUser}
          isProcessing={false}
          targetActive
        />,
      );

      expect(screen.getByText("Reactivate User")).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: "Reactivate" }),
      ).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Deactivate" }),
      ).not.toBeInTheDocument();
    });

    it("shows the ownership override switch for a SCIM-managed user being reactivated", () => {
      render(
        <DeactivateUserModal
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          user={scimUser}
          isProcessing={false}
          targetActive
        />,
      );

      expect(screen.getByText("Override ownership guard")).toBeInTheDocument();
    });

    it("calls onConfirm(true) when reactivating a SCIM-managed user with the override switch on", () => {
      const onConfirm = vi.fn();
      render(
        <DeactivateUserModal
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={onConfirm}
          user={scimUser}
          isProcessing={false}
          targetActive
        />,
      );

      fireEvent.click(screen.getByRole("switch"));
      fireEvent.click(screen.getByRole("button", { name: "Reactivate" }));

      expect(onConfirm).toHaveBeenCalledWith(true);
    });

    it("shows 'Reactivating...' while processing", () => {
      render(
        <DeactivateUserModal
          isOpen={true}
          onClose={vi.fn()}
          onConfirm={vi.fn()}
          user={manualUser}
          isProcessing={true}
          targetActive
        />,
      );

      expect(
        screen.getByRole("button", { name: "Reactivating..." }),
      ).toBeDisabled();
    });
  });
});
