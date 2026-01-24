import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useRuntimeConfig, RuntimeConfigContext } from "./use-runtime-config";

describe("useRuntimeConfig", () => {
  it("returns config when used within provider", () => {
    const mockConfig = { basePath: "/v1" };
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <RuntimeConfigContext value={mockConfig as any}>
        {children}
      </RuntimeConfigContext>
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
