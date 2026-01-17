import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { NotFoundPage } from "./not-found-page";

const mockNavigate = vi.fn();
vi.mock("react-router", () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock("../../shared/components/page/page-container", () => ({
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <div data-testid="page-container" title={title}>{children}</div>
  ),
}));

describe("NotFoundPage", () => {
  it("renders correctly", () => {
    render(<NotFoundPage />);
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByText("Oops! The page you are looking for does not exist.")).toBeInTheDocument();
  });

  it("navigates to profile on button click", () => {
    render(<NotFoundPage />);

    fireEvent.click(screen.getByText("Go to My Profile"));

    expect(mockNavigate).toHaveBeenCalledWith("/user");
  });
});
