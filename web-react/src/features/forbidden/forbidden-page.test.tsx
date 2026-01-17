import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ForbiddenPage from "./forbidden-page";

vi.mock("../../core/components/main-layout", () => ({
  default: ({ children }: any) => <div data-testid="main-layout">{children}</div>,
}));

describe("ForbiddenPage", () => {
  it("renders correctly", () => {
    render(<ForbiddenPage />);
    expect(screen.getByText("Access Denied")).toBeInTheDocument();
    expect(screen.getByText("Sorry, you do not have permission to view this page.")).toBeInTheDocument();
  });
});
