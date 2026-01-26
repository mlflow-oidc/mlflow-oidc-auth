import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RuntimeConfigProvider } from "./runtime-config-provider";
import { useRuntimeConfig } from "./use-runtime-config";

const TestComponent = () => {
  const config = useRuntimeConfig();
  return <div>Base Path: {config.basePath}</div>;
};

import type { RuntimeConfig } from "../services/runtime-config";

describe("RuntimeConfigProvider", () => {
  it("provides config to children", () => {
    const mockConfig: RuntimeConfig = {
      authenticated: true,
      basePath: "/test-base",
      uiPath: "/ui",
      provider: "oidc",
    };
    render(
      <RuntimeConfigProvider config={mockConfig}>
        <TestComponent />
      </RuntimeConfigProvider>,
    );
    expect(screen.getByText("Base Path: /test-base")).toBeDefined();
  });
});
