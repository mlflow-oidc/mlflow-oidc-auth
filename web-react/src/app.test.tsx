import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { MemoryRouter } from "react-router";
import App from "./app";

// Mock all lazy loaded components
vi.mock("./features/auth/auth-page", () => ({
  default: () => <div>AuthPage</div>,
}));
vi.mock("./features/experiments/experiments-page", () => ({
  default: () => <div>ExperimentsPage</div>,
}));
vi.mock("./features/experiments/experiment-permissions-page", () => ({
  default: () => <div>ExperimentPermissionsPage</div>,
}));
vi.mock("./features/ai-gateway/ai-endpoints-page", () => ({
  default: () => <div>AiEndpointsPage</div>,
}));
vi.mock("./features/ai-gateway/ai-endpoints-permission-page", () => ({
  default: () => <div>AiEndpointsPermissionPage</div>,
}));
vi.mock("./features/ai-gateway/ai-secrets-page", () => ({
  default: () => <div>AiSecretsPage</div>,
}));
vi.mock("./features/ai-gateway/ai-models-page", () => ({
  default: () => <div>AiModelsPage</div>,
}));
vi.mock("./features/groups/groups-page", () => ({
  default: () => <div>GroupsPage</div>,
}));
vi.mock("./features/groups/group-permissions-page", () => ({
  default: () => <div>GroupPermissionsPage</div>,
}));
vi.mock("./features/models/models-page", () => ({
  default: () => <div>ModelsPage</div>,
}));
vi.mock("./features/models/model-permissions-page", () => ({
  default: () => <div>ModelPermissionsPage</div>,
}));
vi.mock("./features/prompts/prompts-page", () => ({
  default: () => <div>PromptsPage</div>,
}));
vi.mock("./features/prompts/prompt-permissions-page", () => ({
  default: () => <div>PromptPermissionsPage</div>,
}));
vi.mock("./features/service-accounts/service-accounts-page", () => ({
  default: () => <div>ServiceAccountsPage</div>,
}));
vi.mock("./features/service-accounts/service-account-permission-page", () => ({
  default: () => <div>ServiceAccountPermissionPage</div>,
}));
vi.mock("./features/trash/trash-page", () => ({
  default: () => <div>TrashPage</div>,
}));
vi.mock("./features/user/user-page", () => ({
  default: () => <div>UserPage</div>,
}));
vi.mock("./features/users/users-page", () => ({
  default: () => <div>UsersPage</div>,
}));
vi.mock("./features/users/user-permissions-page", () => ({
  default: () => <div>UserPermissionsPage</div>,
}));
vi.mock("./features/webhooks/webhooks-page", () => ({
  default: () => <div>WebhooksPage</div>,
}));
vi.mock("./features/not-found/not-found-page", () => ({
  default: () => <div>NotFoundPage</div>,
}));
vi.mock("./features/forbidden/forbidden-page", () => ({
  default: () => <div>ForbiddenPage</div>,
}));

// Mock wrappers
vi.mock("./features/auth/components/protected-route", () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
vi.mock("./features/auth/components/redirect-if-auth", () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
vi.mock("./core/components/main-layout", () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));
vi.mock("./shared/components/loading-spinner", () => ({
  LoadingSpinner: () => <div>Loading...</div>,
}));

describe("App Routing", () => {
  it("renders AuthPage on /auth", async () => {
    render(
      <MemoryRouter initialEntries={["/auth"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("AuthPage")).toBeInTheDocument();
  });

  it("renders ExperimentsPage on /experiments", async () => {
    render(
      <MemoryRouter initialEntries={["/experiments"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("ExperimentsPage")).toBeInTheDocument();
  });

  it("renders ExperimentPermissionsPage on /experiments/:id", async () => {
    render(
      <MemoryRouter initialEntries={["/experiments/123"]}>
        <App />
      </MemoryRouter>,
    );
    expect(
      await screen.findByText("ExperimentPermissionsPage"),
    ).toBeInTheDocument();
  });

  it("renders AiEndpointsPage on /ai-gateway/endpoints", async () => {
    render(
      <MemoryRouter initialEntries={["/ai-gateway/endpoints"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("AiEndpointsPage")).toBeInTheDocument();
  });

  it("renders AiEndpointsPermissionPage on /ai-gateway/endpoints/:name", async () => {
    render(
      <MemoryRouter initialEntries={["/ai-gateway/endpoints/test-endpoint"]}>
        <App />
      </MemoryRouter>,
    );
    expect(
      await screen.findByText("AiEndpointsPermissionPage"),
    ).toBeInTheDocument();
  });

  it("renders AiSecretsPage on /ai-gateway/secrets", async () => {
    render(
      <MemoryRouter initialEntries={["/ai-gateway/secrets"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("AiSecretsPage")).toBeInTheDocument();
  });

  it("renders AiModelsPage on /ai-gateway/models", async () => {
    render(
      <MemoryRouter initialEntries={["/ai-gateway/models"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("AiModelsPage")).toBeInTheDocument();
  });

  it("renders NotFoundPage on unknown route", async () => {
    render(
      <MemoryRouter initialEntries={["/unknown"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByText("NotFoundPage")).toBeInTheDocument();
  });
});
