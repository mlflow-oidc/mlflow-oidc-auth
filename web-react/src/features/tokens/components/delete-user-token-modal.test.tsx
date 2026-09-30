import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DeleteUserTokenModal } from "./delete-user-token-modal";
import type { UserToken } from "../../../shared/types/user";

const token: UserToken = {
  id: 1,
  name: "ci",
  token_prefix: null,
  created_at: "2026-09-01T00:00:00Z",
  created_by: null,
  expires_at: "2027-01-01T23:59:59Z",
  last_used_at: null,
  active: true,
};

describe("DeleteUserTokenModal", () => {
  it("renders nothing without a token", () => {
    const { container } = render(
      <DeleteUserTokenModal
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        token={null}
        isProcessing={false}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("names the token and confirms or cancels", () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    render(
      <DeleteUserTokenModal
        isOpen
        onClose={onClose}
        onConfirm={onConfirm}
        token={token}
        isProcessing={false}
      />,
    );
    expect(screen.getByText("ci")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete token" }));
    expect(onConfirm).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("disables both actions while processing", () => {
    render(
      <DeleteUserTokenModal
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        token={token}
        isProcessing
      />,
    );
    expect(screen.getByRole("button", { name: "Deleting..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });
});
