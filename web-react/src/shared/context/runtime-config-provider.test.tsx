import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RuntimeConfigProvider } from "./runtime-config-provider";
import { useRuntimeConfig } from "./use-runtime-config";

const TestComponent = () => {
    const config = useRuntimeConfig();
    return <div>Base Path: {config.basePath}</div>;
};

describe("RuntimeConfigProvider", () => {
    it("provides config to children", () => {
        const mockConfig = { authenticated: true, basePath: "/test-base" };
        render(
            <RuntimeConfigProvider config={mockConfig as any}>
                <TestComponent />
            </RuntimeConfigProvider>
        );
        expect(screen.getByText("Base Path: /test-base")).toBeDefined();
    });
});
