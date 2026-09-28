import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { RevokeAllUserTokensModal } from "./revoke-all-user-tokens-modal";

describe("RevokeAllUserTokensModal", () => {
  it("states the count and user and confirms", () => {
    const onConfirm = vi.fn();
    render(
      <RevokeAllUserTokensModal
        isOpen
        onClose={vi.fn()}
        onConfirm={onConfirm}
        username="bob"
        tokenCount={1}
        isProcessing={false}
      />,
    );
    expect(screen.getByText(/All 1 token of/)).toHaveTextContent("bob");
    fireEvent.click(screen.getByRole("button", { name: "Revoke all tokens" }));
    expect(onConfirm).toHaveBeenCalled();
  });

  it("pluralizes and disables while processing", () => {
    render(
      <RevokeAllUserTokensModal
        isOpen
        onClose={vi.fn()}
        onConfirm={vi.fn()}
        username="bob"
        tokenCount={3}
        isProcessing
      />,
    );
    expect(screen.getByText(/All 3 tokens of/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Revoking..." })).toBeDisabled();
  });
});
