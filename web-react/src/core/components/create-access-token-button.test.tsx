import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { CreateAccessTokenButton } from "./create-access-token-button";

vi.mock("./access-token-modal", () => ({
  AccessTokenModal: () => <div data-testid="access-token-modal">Modal Content</div>,
}));

describe("CreateAccessTokenButton", () => {
  it("renders button", () => {
    render(<CreateAccessTokenButton username="testuser" />);
    expect(screen.getByRole("button", { name: "Create Access Token" })).toBeInTheDocument();
  });

  it("opens modal on click", () => {
    render(<CreateAccessTokenButton username="testuser" />);

    expect(screen.queryByTestId("access-token-modal")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Create Access Token" }));

    expect(screen.queryByTestId("access-token-modal")).toBeInTheDocument();
  });
});
