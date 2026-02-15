import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AiModelsPage from "./ai-models-page";
import { useAllGatewayModels } from "../../core/hooks/use-all-gateway-models";
import { MemoryRouter } from "react-router";
import { useRuntimeConfig } from "../../shared/context/use-runtime-config";
import type { RuntimeConfig } from "../../shared/services/runtime-config";

// Mock hooks
vi.mock("../../core/hooks/use-all-gateway-models");
vi.mock("../../shared/context/use-runtime-config");

const mockModels = [
  {
    name: "model-1",
    source: "openai",
  },
  {
    name: "model-2",
    source: "anthropic",
  },
];

describe("AiModelsPage", () => {
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
    vi.mocked(useAllGatewayModels).mockReturnValue({
      isLoading: true,
      error: null,
      allGatewayModels: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiModelsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("Loading AI models list...")).toBeInTheDocument();
  });

  it("renders error state", () => {
    vi.mocked(useAllGatewayModels).mockReturnValue({
      isLoading: false,
      error: new Error("Test error"),
      allGatewayModels: [],
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiModelsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/Error: Test error/i)).toBeInTheDocument();
  });

  it("renders models list", () => {
    vi.mocked(useAllGatewayModels).mockReturnValue({
      isLoading: false,
      error: null,
      allGatewayModels: mockModels,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiModelsPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("model-1")).toBeInTheDocument();
    expect(screen.getByText("model-2")).toBeInTheDocument();
    expect(screen.getByText("openai")).toBeInTheDocument();
  });

  it("filters models by search term", () => {
    vi.mocked(useAllGatewayModels).mockReturnValue({
      isLoading: false,
      error: null,
      allGatewayModels: mockModels,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiModelsPage />
      </MemoryRouter>,
    );

    const searchInput = screen.getByPlaceholderText("Search AI models...");
    fireEvent.change(searchInput, { target: { value: "model-1" } });
    fireEvent.submit(searchInput);

    expect(screen.getByText("model-1")).toBeInTheDocument();
    expect(screen.queryByText("model-2")).not.toBeInTheDocument();
  });

  it("renders permission buttons", () => {
    vi.mocked(useAllGatewayModels).mockReturnValue({
      isLoading: false,
      error: null,
      allGatewayModels: mockModels,
      refresh: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AiModelsPage />
      </MemoryRouter>,
    );

    const permissionButtons = screen.getAllByText("Manage permissions");
    expect(permissionButtons).toHaveLength(2);
  });
});
