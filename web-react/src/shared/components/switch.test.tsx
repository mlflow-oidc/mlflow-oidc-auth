import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { Switch } from "./switch";

describe("Switch", () => {
  it("renders correctly", () => {
    render(<Switch checked={false} onChange={() => {}} label="Toggle me" />);
    expect(screen.getByRole("switch")).toBeInTheDocument();
    expect(screen.getByText("Toggle me")).toBeInTheDocument();
    expect(screen.getByText("OFF")).toBeVisible(); // Opacity check might be tricky with jest-dom sometimes, but let's assume standard visibility check works if opacity is handled
    // Actually opacity-0 makes it not visible to user but present in DOM
  });

  it("toggles state on click", () => {
    const handleChange = vi.fn();
    render(<Switch checked={false} onChange={handleChange} />);
    
    fireEvent.click(screen.getByRole("switch").parentElement!);
    expect(handleChange).toHaveBeenCalledWith(true);
  });

  it("does not toggle when disabled", () => {
    const handleChange = vi.fn();
    render(<Switch checked={false} onChange={handleChange} disabled />);
    
    fireEvent.click(screen.getByRole("switch").parentElement!);
    expect(handleChange).not.toHaveBeenCalled();
  });
  
  it("shows ON label when checked", () => {
    render(<Switch checked={true} onChange={() => {}} />);
    // "ON" should have opacity-100
    const onLabel = screen.getByText("ON");
    expect(onLabel).toHaveClass("opacity-100");
  });
});
