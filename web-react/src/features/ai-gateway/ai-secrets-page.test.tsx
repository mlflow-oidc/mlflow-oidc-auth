import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AiSecretsPage from "./ai-secrets-page";
import { useAllGatewaySecrets } from "../../core/hooks/use-all-gateway-secrets";
import { MemoryRouter } from "react-router";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import type { RuntimeConfig } from "../../shared/services/runtime-config";

// Mock hooks
vi.mock("../../core/hooks/use-all-gateway-secrets");
vi.mock("../../shared/context/use-runtime-config");

const mockSecrets = [
  {
    key: "secret-1",
  },
  {
    key: "secret-2",
  },
];

describe("AiSecretsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useRuntimeConfig).mockReturnValue({
      basePath: "",
      uiPath: "/",
      provider: "local",
      authenticated: true,
      gen_ai_gateway_enabled: true,
    } as RuntimeConfig);
  });

  it("renders loading state", () => {
    vi.mocked(useAllGatewaySecrets).mockReturnValue({
      isLoading: true,
      error: null,
      allGatewaySecrets: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiSecretsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Loading secrets list...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    vi.mocked(useAllGatewaySecrets).mockReturnValue({
      isLoading: false,
      error: new Error("Test error"),
      allGatewaySecrets: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiSecretsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Error: Test error/i)).toBeInTheDocument();
  });

  it("renders secrets list", () => {
    vi.mocked(useAllGatewaySecrets).mockReturnValue({
      isLoading: false,
      error: null,
      allGatewaySecrets: mockSecrets,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiSecretsPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("secret-1")).toBeInTheDocument();
    expect(screen.getByText("secret-2")).toBeInTheDocument();
  });

  it("filters secrets by search term", () => {
    vi.mocked(useAllGatewaySecrets).mockReturnValue({
      isLoading: false,
      error: null,
      allGatewaySecrets: mockSecrets,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiSecretsPage />
      </MemoryRouter>,
    );

    const searchInput = screen.getByPlaceholderText("Search secrets...");
    fireEvent.change(searchInput, { target: { value: "secret-1" } });
    fireEvent.submit(searchInput);

    expect(screen.getByText("secret-1")).toBeInTheDocument();
    expect(screen.queryByText("secret-2")).not.toBeInTheDocument();
  });

  it("renders permission buttons", () => {
    vi.mocked(useAllGatewaySecrets).mockReturnValue({
      isLoading: false,
      error: null,
      allGatewaySecrets: mockSecrets,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiSecretsPage />
      </MemoryRouter>,
    );

    const permissionButtons = screen.getAllByText("Manage permissions");
    expect(permissionButtons).toHaveLength(2);
  });
});
