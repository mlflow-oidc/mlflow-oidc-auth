import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AuthPage } from "./auth-page";

const mockUseAuthErrors = vi.fn();
const mockUseRuntimeConfig = vi.fn();

vi.mock("../../shared/context/use-runtime-config", () => ({
  useRuntimeConfig: () => mockUseRuntimeConfig(),
}));

vi.mock("./hooks/use-auth-errors", () => ({
  useAuthErrors: () => mockUseAuthErrors(),
}));

describe("AuthPage", () => {
  beforeEach(() => {
    mockUseRuntimeConfig.mockReturnValue({
      provider: "Sign in with OIDC",
      basePath: "/api",
    });
    mockUseAuthErrors.mockReturnValue([]);
  });

  it("renders sign in button with correct link", () => {
    render(<AuthPage />);

    expect(screen.getByText("Sign in")).toBeInTheDocument();

    const button = screen.getByText("Sign in with OIDC");
    expect(button).toBeInTheDocument();

    const anchor = button.closest("a");
    expect(anchor).toHaveAttribute("href", "/api/login");
  });

  it("renders errors when present", () => {
    mockUseAuthErrors.mockReturnValue(["Error 1", "Error 2"]);

    render(<AuthPage />);

    expect(screen.getByText("Error 1")).toBeInTheDocument();
    expect(screen.getByText("Error 2")).toBeInTheDocument();

    const statusDiv = screen.getByRole("status");
    expect(statusDiv).toHaveClass("bg-red-50");
  });

  it("renders default message when no errors", () => {
    render(<AuthPage />);
    expect(screen.getByText("Use the button below to sign in.")).toBeInTheDocument();
  });
});
