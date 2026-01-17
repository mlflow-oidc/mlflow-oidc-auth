import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TokenInfoBlock } from "./token-info-block";

vi.mock("../../core/components/create-access-token-button", () => ({
  CreateAccessTokenButton: () => <button>Create Token</button>,
}));

describe("TokenInfoBlock", () => {
  it("renders with no token", () => {
    render(<TokenInfoBlock username="user" />);
    expect(screen.getByText("No access token created yet")).toBeInTheDocument();
    expect(screen.getByText("Create Token")).toBeInTheDocument();
  });

  it("renders with token info", () => {
    const date = new Date("2023-01-01T12:00:00Z");
    render(<TokenInfoBlock username="user" passwordExpiration={date.toISOString()} />);
    
    expect(screen.getByText(/Token expires on:/)).toBeInTheDocument();
    expect(screen.getByText(/Jan 1, 2023/)).toBeInTheDocument(); // Depends on locale, but en-US is standard in jsdom usually
  });
});
