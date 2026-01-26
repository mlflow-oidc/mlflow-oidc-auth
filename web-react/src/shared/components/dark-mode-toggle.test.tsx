import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import DarkModeToggle from "./dark-mode-toggle";

const mockToggleTheme = vi.fn();
const mockUseTheme = vi.fn<() => { isDark: boolean; toggleTheme: () => void }>();

vi.mock("../utils/theme-utils", () => ({
  useTheme: () => mockUseTheme(),
}));

describe("DarkModeToggle", () => {
  beforeEach(() => {
    mockToggleTheme.mockReset();
    mockUseTheme.mockReset();
  });

  it("renders with moon icon when dark mode is enabled", () => {
    mockUseTheme.mockReturnValue({
      isDark: true,
      toggleTheme: mockToggleTheme,
    });

    render(<DarkModeToggle />);
    const button = screen.getByRole("button", { name: "Switch to Light Mode" });
    expect(button).toBeInTheDocument();
    // FontAwesome icon check - usually we check for the svg or specific class
    expect(document.querySelector(".fa-moon")).toBeInTheDocument();
  });

  it("renders with sun icon when light mode is enabled", () => {
    mockUseTheme.mockReturnValue({
      isDark: false,
      toggleTheme: mockToggleTheme,
    });

    render(<DarkModeToggle />);
    const button = screen.getByRole("button", { name: "Switch to Dark Mode" });
    expect(button).toBeInTheDocument();
    expect(document.querySelector(".fa-sun")).toBeInTheDocument();
  });

  it("calls toggleTheme when clicked", () => {
    mockUseTheme.mockReturnValue({
      isDark: false,
      toggleTheme: mockToggleTheme,
    });

    render(<DarkModeToggle />);
    fireEvent.click(screen.getByRole("button"));
    expect(mockToggleTheme).toHaveBeenCalledTimes(1);
  });
});
