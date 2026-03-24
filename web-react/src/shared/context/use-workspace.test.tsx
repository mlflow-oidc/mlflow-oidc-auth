import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useWorkspace, WorkspaceContext } from "./use-workspace";
import type { WorkspaceContextValue } from "./use-workspace";

describe("useWorkspace", () => {
  it("throws when used outside WorkspaceProvider", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => renderHook(() => useWorkspace())).toThrow(
      "useWorkspace must be used inside <WorkspaceProvider>",
    );

    consoleSpy.mockRestore();
  });

  it("returns context value when inside provider", () => {
    const mockValue: WorkspaceContextValue = {
      selectedWorkspace: "test-ws",
      setSelectedWorkspace: vi.fn(),
    };
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <WorkspaceContext value={mockValue}>{children}</WorkspaceContext>
    );
    const { result } = renderHook(() => useWorkspace(), { wrapper });
    expect(result.current.selectedWorkspace).toBe("test-ws");
    expect(result.current.setSelectedWorkspace).toBeDefined();
  });

  it("returns null selectedWorkspace when set to null", () => {
    const mockValue: WorkspaceContextValue = {
      selectedWorkspace: null,
      setSelectedWorkspace: vi.fn(),
    };
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <WorkspaceContext value={mockValue}>{children}</WorkspaceContext>
    );
    const { result } = renderHook(() => useWorkspace(), { wrapper });
    expect(result.current.selectedWorkspace).toBeNull();
  });
});
