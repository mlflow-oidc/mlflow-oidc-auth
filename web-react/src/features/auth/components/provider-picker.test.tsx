import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { ProviderPicker } from "./provider-picker";
import type { IdentityProvider } from "../services/provider-service";

const provider = (
  id: string,
  displayName: string,
  type: string = "oidc",
): IdentityProvider => ({
  id,
  display_name: displayName,
  type,
  login_url: `/api/login/${id}`,
});

describe("ProviderPicker", () => {
  it("renders one button per provider with the server's login URL", () => {
    render(
      <ProviderPicker
        providers={[provider("entra", "Entra ID"), provider("okta", "Okta")]}
        next={null}
        basePath=""
      />,
    );

    expect(screen.getByRole("link", { name: "Entra ID" })).toHaveAttribute(
      "href",
      "/api/login/entra",
    );
    expect(screen.getByRole("link", { name: "Okta" })).toHaveAttribute(
      "href",
      "/api/login/okta",
    );
  });

  it("carries ?next= through the login URL", () => {
    render(
      <ProviderPicker
        providers={[provider("entra", "Entra ID")]}
        next="/oidc/ui/models"
        basePath=""
      />,
    );

    expect(screen.getByRole("link", { name: "Entra ID" })).toHaveAttribute(
      "href",
      "/api/login/entra?next=%2Foidc%2Fui%2Fmodels",
    );
  });

  it("labels the SAML entry in a mixed list without labeling the OIDC ones beside it (#330)", () => {
    render(
      <ProviderPicker
        providers={[
          provider("corp", "Corporate SSO", "saml"),
          provider("entra", "Entra ID", "oidc"),
        ]}
        next={null}
        basePath=""
      />,
    );

    expect(screen.getByTestId("provider-kind-corp")).toHaveTextContent(
      "SAML",
    );
    expect(
      screen.queryByTestId("provider-kind-entra"),
    ).not.toBeInTheDocument();
  });

  it("shows no kind label at all when every provider is OIDC", () => {
    render(
      <ProviderPicker
        providers={[provider("entra", "Entra ID"), provider("okta", "Okta")]}
        next={null}
        basePath=""
      />,
    );

    expect(screen.queryByText("SAML")).not.toBeInTheDocument();
  });

  it("renders a provider of an unknown type without a kind label", () => {
    // #330 says the shape doesn't change for a type this picker has never heard of — it just
    // renders, unlabeled, same as it always has.
    render(
      <ProviderPicker
        providers={[provider("legacy", "Legacy SSO", "ldap")]}
        next={null}
        basePath=""
      />,
    );

    expect(
      screen.getByRole("link", { name: "Legacy SSO" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("provider-kind-legacy"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("SAML")).not.toBeInTheDocument();
  });

  it("prefixes a login URL with basePath when the two disagree (untrusted proxy hop)", () => {
    render(
      <ProviderPicker
        providers={[provider("entra", "Entra ID")]}
        next={null}
        basePath="/mlflow"
      />,
    );

    expect(screen.getByRole("link", { name: "Entra ID" })).toHaveAttribute(
      "href",
      "/mlflow/api/login/entra",
    );
  });

  it("leaves a login URL alone when it is already under basePath", () => {
    render(
      <ProviderPicker
        providers={[
          {
            id: "entra",
            display_name: "Entra ID",
            type: "oidc",
            login_url: "/mlflow/api/login/entra",
          },
        ]}
        next={null}
        basePath="/mlflow"
      />,
    );

    expect(screen.getByRole("link", { name: "Entra ID" })).toHaveAttribute(
      "href",
      "/mlflow/api/login/entra",
    );
  });
});
