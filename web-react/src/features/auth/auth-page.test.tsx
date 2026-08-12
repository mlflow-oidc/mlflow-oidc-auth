import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AuthPage } from "./auth-page";

import type { RuntimeConfig } from "../../shared/services/runtime-config";
import type { Mock } from "vitest";
import type { ProvidersState } from "./hooks/use-providers";

const mockUseAuthErrors: Mock<() => string[]> = vi.fn();
const mockUseRuntimeConfig: Mock<() => RuntimeConfig> = vi.fn();

vi.mock("../../shared/context/use-runtime-config", () => ({
  useRuntimeConfig: () => mockUseRuntimeConfig(),
}));

vi.mock("./hooks/use-auth-errors", () => ({
  useAuthErrors: () => mockUseAuthErrors(),
}));

vi.mock("../../shared/components/dark-mode-toggle", () => ({
  default: () => <div data-testid="dark-mode-toggle" />,
}));

// The provider list is fetched (#317). Default to none, which is what a server from before
// #316 reports — and the case every existing assertion below describes.
const mockUseProviders: Mock<() => ProvidersState> = vi.fn(() => ({
  providers: [],
  loading: false,
}));

vi.mock("./hooks/use-providers", () => ({
  useProviders: () => mockUseProviders(),
}));

describe("AuthPage", () => {
  beforeEach(() => {
    mockUseRuntimeConfig.mockReturnValue({
      provider: "Sign in with OIDC",
      basePath: "/api",
      uiPath: "/ui",
      authenticated: false,
      gen_ai_gateway_enabled: false,
      workspaces_enabled: false,
    });
    mockUseAuthErrors.mockReturnValue([]);
  });

  it("renders sign in button with correct link", () => {
    render(<AuthPage />);

    expect(screen.getByText("MLflow")).toBeInTheDocument();

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

    const alertDiv = screen.getByRole("alert");
    expect(alertDiv).toHaveClass("bg-red-100");
  });

  it("renders footer with copyright and sponsor link", () => {
    render(<AuthPage />);

    const currentYear = new Date().getFullYear();
    expect(
      screen.getByText(
        new RegExp(`© ${currentYear} Kharkevich Engineering Lab`),
      ),
    ).toBeInTheDocument();

    const sponsorLink = screen.getByText("Support the project");
    expect(sponsorLink).toBeInTheDocument();
    expect(sponsorLink.closest("a")).toHaveAttribute(
      "href",
      "https://github.com/sponsors/mlflow-oidc?o=esb",
    );
  });

  it("renders dark mode toggle", () => {
    render(<AuthPage />);
    expect(screen.getByTestId("dark-mode-toggle")).toBeInTheDocument();
  });
});

describe("AuthPage provider picker (#317)", () => {
  beforeEach(() => {
    mockUseRuntimeConfig.mockReturnValue({
      provider: "Sign in with OIDC",
      basePath: "/api",
      uiPath: "/ui",
      authenticated: false,
      gen_ai_gateway_enabled: false,
      workspaces_enabled: false,
    });
    mockUseAuthErrors.mockReturnValue([]);
    mockUseProviders.mockReturnValue({ providers: [], loading: false });
    window.history.replaceState({}, "", "/");
  });

  const provider = (id: string, displayName: string) => ({
    id,
    display_name: displayName,
    type: "oidc",
    login_url: `/api/login/${id}`,
  });

  it("renders the page it always has when no providers are reported", () => {
    // A server from before #316 has no /providers endpoint at all.
    render(<AuthPage />);

    const link = screen.getByRole("link", { name: "Sign in with OIDC" });
    expect(link).toHaveAttribute("href", "/api/login");
    expect(screen.queryByText("Sign in with")).not.toBeInTheDocument();
  });

  it("renders one button and no picker chrome for a single provider", () => {
    mockUseProviders.mockReturnValue({
      providers: [provider("default", "Login with OIDC")],
      loading: false,
    });

    render(<AuthPage />);

    expect(
      screen.getByRole("link", { name: "Login with OIDC" }),
    ).toHaveAttribute("href", "/api/login/default");
    expect(screen.queryByText("Sign in with")).not.toBeInTheDocument();
  });

  it("renders one button per provider when there are several", () => {
    mockUseProviders.mockReturnValue({
      providers: [provider("entra", "Entra ID"), provider("okta", "Okta")],
      loading: false,
    });

    render(<AuthPage />);

    expect(screen.getByText("Sign in with")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Entra ID" })).toHaveAttribute(
      "href",
      "/api/login/entra",
    );
    expect(screen.getByRole("link", { name: "Okta" })).toHaveAttribute(
      "href",
      "/api/login/okta",
    );
  });

  it("carries ?next= through a chosen provider", () => {
    window.history.replaceState({}, "", "/?next=/oidc/ui/models");
    mockUseProviders.mockReturnValue({
      providers: [provider("entra", "Entra ID"), provider("okta", "Okta")],
      loading: false,
    });

    render(<AuthPage />);

    expect(screen.getByRole("link", { name: "Entra ID" })).toHaveAttribute(
      "href",
      "/api/login/entra?next=%2Foidc%2Fui%2Fmodels",
    );
  });

  it("carries ?next= through the single-provider button too", () => {
    window.history.replaceState({}, "", "/?next=/oidc/ui/models");
    mockUseProviders.mockReturnValue({
      providers: [provider("default", "Login with OIDC")],
      loading: false,
    });

    render(<AuthPage />);

    expect(
      screen.getByRole("link", { name: "Login with OIDC" }),
    ).toHaveAttribute("href", "/api/login/default?next=%2Foidc%2Fui%2Fmodels");
  });

  it("does not know what kind of provider it is drawing", () => {
    // #330 adds SAML providers; they should appear without this page changing.
    mockUseProviders.mockReturnValue({
      providers: [
        {
          id: "corp",
          display_name: "Corporate SSO",
          type: "saml",
          login_url: "/api/login/corp",
        },
        provider("entra", "Entra ID"),
      ],
      loading: false,
    });

    render(<AuthPage />);

    expect(screen.getByRole("link", { name: "Corporate SSO" })).toHaveAttribute(
      "href",
      "/api/login/corp",
    );
  });

  it("offers nothing to click until the list has arrived", () => {
    // The fallback button names the *default* provider. Clicking it in the moment before the
    // list arrives would start a login against an IdP this user may not belong to.
    mockUseProviders.mockReturnValue({ providers: [], loading: true });

    render(<AuthPage />);

    expect(
      screen.queryByRole("link", { name: /sign in/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("providers-loading")).toBeDisabled();
  });

  it("still shows errors alongside the picker", () => {
    mockUseAuthErrors.mockReturnValue(["User is not allowed to login"]);
    mockUseProviders.mockReturnValue({
      providers: [provider("entra", "Entra ID"), provider("okta", "Okta")],
      loading: false,
    });

    render(<AuthPage />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "User is not allowed to login",
    );
    expect(screen.getByRole("link", { name: "Entra ID" })).toBeInTheDocument();
  });
});
