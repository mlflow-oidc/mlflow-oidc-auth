import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useRuntimeConfig, RuntimeConfigContext } from "./use-runtime-config";

import type { RuntimeConfig } from "../services/runtime-config";

describe("useRuntimeConfig", () => {
  it("returns config when used within provider", () => {
    const mockConfig: RuntimeConfig = {
      basePath: "/v1",
      uiPath: "/ui",
      provider: "oidc",
      authenticated: true,
    };
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <RuntimeConfigContext value={mockConfig}>{children}</RuntimeConfigContext>
    );

    const { result } = renderHook(() => useRuntimeConfig(), { wrapper });
    expect(result.current).toEqual(mockConfig);
  });

  it("throws error when used outside provider", () => {
    // Suppress console.error for expected throw
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => renderHook(() => useRuntimeConfig())).toThrow(
      "useRuntimeConfig must be used within a RuntimeConfigProvider",
    );

    consoleSpy.mockRestore();
  });
});
