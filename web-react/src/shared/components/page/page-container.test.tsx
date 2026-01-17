import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PageContainer from "./page-container";

describe("PageContainer", () => {
    it("renders title and children", () => {
        render(
            <PageContainer title="Test Page">
                <div>Child Content</div>
            </PageContainer>
        );
        
        expect(screen.getByText("Test Page")).toBeDefined();
        expect(screen.getByText("Child Content")).toBeDefined();
    });
});
