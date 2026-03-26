import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import {
  WorkspaceProvider,
  getActiveWorkspace,
  setActiveWorkspace,
} from "./workspace-context";
import { useWorkspace } from "./use-workspace";

// Create a proper localStorage mock since jsdom doesn't provide one
const localStorageStore: Record<string, string> = {};
const localStorageMock = {
  getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageStore[key] = value;
  }),
  removeItem: vi.fn((key: string) => {
    delete localStorageStore[key];
  }),
};

describe("workspace-context module-level functions", () => {
  afterEach(() => {
    setActiveWorkspace(null);
  });

  it("getActiveWorkspace returns null by default", () => {
    setActiveWorkspace(null);
    expect(getActiveWorkspace()).toBeNull();
  });

  it("setActiveWorkspace updates the module-level workspace", () => {
    setActiveWorkspace("my-workspace");
    expect(getActiveWorkspace()).toBe("my-workspace");
  });

  it("setActiveWorkspace(null) clears the workspace", () => {
    setActiveWorkspace("my-workspace");
    setActiveWorkspace(null);
    expect(getActiveWorkspace()).toBeNull();
  });
});

describe("WorkspaceProvider", () => {
  beforeEach(() => {
    Object.keys(localStorageStore).forEach(
      (key) => delete localStorageStore[key],
    );
    Object.defineProperty(window, "localStorage", {
      value: localStorageMock,
      writable: true,
      configurable: true,
    });
    vi.clearAllMocks();
    setActiveWorkspace(null);
  });

  afterEach(() => {
    Object.keys(localStorageStore).forEach(
      (key) => delete localStorageStore[key],
    );
    setActiveWorkspace(null);
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <WorkspaceProvider>{children}</WorkspaceProvider>
  );

  it("initializes to null when localStorage is empty", () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });
    expect(result.current.selectedWorkspace).toBeNull();
  });

  it("initializes from localStorage if value exists", () => {
    localStorageStore["mlflow-oidc-workspace"] = "saved-workspace";

    const { result } = renderHook(() => useWorkspace(), { wrapper });
    expect(result.current.selectedWorkspace).toBe("saved-workspace");
  });

  it("setSelectedWorkspace updates value and persists to localStorage", async () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setSelectedWorkspace("new-workspace");
    });

    expect(result.current.selectedWorkspace).toBe("new-workspace");

    await waitFor(() => {
      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "mlflow-oidc-workspace",
        "new-workspace",
      );
    });
  });

  it("setSelectedWorkspace(null) removes from localStorage", async () => {
    localStorageStore["mlflow-oidc-workspace"] = "existing-workspace";
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setSelectedWorkspace(null);
    });

    expect(result.current.selectedWorkspace).toBeNull();

    await waitFor(() => {
      expect(localStorageMock.removeItem).toHaveBeenCalledWith(
        "mlflow-oidc-workspace",
      );
    });
  });

  it("syncs module-level state via setActiveWorkspace on mount", async () => {
    localStorageStore["mlflow-oidc-workspace"] = "synced-workspace";
    renderHook(() => useWorkspace(), { wrapper });

    await waitFor(() => {
      expect(getActiveWorkspace()).toBe("synced-workspace");
    });
  });

  it("updates module-level state when workspace changes", async () => {
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    act(() => {
      result.current.setSelectedWorkspace("changed-workspace");
    });

    await waitFor(() => {
      expect(getActiveWorkspace()).toBe("changed-workspace");
    });
  });

  it("updates module-level state synchronously before child effects run", () => {
    // This test verifies the fix for the bug where child effects
    // (e.g. useApi re-fetch) would read stale workspace values because
    // React runs child effects before parent effects.
    const { result } = renderHook(() => useWorkspace(), { wrapper });

    // After calling setSelectedWorkspace, getActiveWorkspace must
    // return the new value immediately — not after effects flush.
    act(() => {
      result.current.setSelectedWorkspace("sync-workspace");
      expect(getActiveWorkspace()).toBe("sync-workspace");
    });
  });

  it("initializes module-level state from localStorage during first render", () => {
    localStorageStore["mlflow-oidc-workspace"] = "eager-workspace";

    // After the first render (inside act), getActiveWorkspace should
    // already have the stored value — set eagerly in useState initializer.
    renderHook(() => useWorkspace(), { wrapper });
    expect(getActiveWorkspace()).toBe("eager-workspace");
  });
});
