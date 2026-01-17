import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { IconButton } from "./icon-button";
import { faHome } from "@fortawesome/free-solid-svg-icons";

describe("IconButton", () => {
  it("renders with icon", () => {
    render(<IconButton icon={faHome} onClick={() => {}} title="Home" />);
    // FontAwesome icon check
    expect(document.querySelector("svg")).toBeInTheDocument();
    // Title is passed to the button
    expect(screen.getByTitle("Home")).toBeInTheDocument();
  });

  it("calls onClick handler", () => {
    const handleClick = vi.fn();
    render(<IconButton icon={faHome} onClick={handleClick} />);
    
    fireEvent.click(screen.getByRole("button"));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it("prevents multiple clicks when disabled", () => {
    const handleClick = vi.fn();
    render(<IconButton icon={faHome} onClick={handleClick} disabled />);
    
    // First, check it is disabled
    expect(screen.getByRole("button")).toBeDisabled();

    // Try to click
    fireEvent.click(screen.getByRole("button"));
    expect(handleClick).not.toHaveBeenCalled();
  });

  it("stops propagation on click", () => {
    const handleWrapperClick = vi.fn();
    const handleButtonClick = vi.fn();

    render(
      <div onClick={handleWrapperClick}>
        <IconButton icon={faHome} onClick={handleButtonClick} />
      </div>
    );

    fireEvent.click(screen.getByRole("button"));
    expect(handleButtonClick).toHaveBeenCalled();
    expect(handleWrapperClick).not.toHaveBeenCalled();
  });
});
