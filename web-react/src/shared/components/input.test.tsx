import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Input } from "./input";

describe("Input", () => {
  it("renders with label", () => {
    render(<Input label="Username" id="username" />);
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
  });

  it("renders with error message", () => {
    render(<Input error="Invalid input" />);
    expect(screen.getByText("Invalid input")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).toHaveClass("border-red-500");
  });

  it("reserves error space", () => {
    // When no error but space reserved, it renders a non-breaking space
    render(<Input reserveErrorSpace />);
    // We can check if the paragraph exists and has invisible class if logic allows,
    // but looking at implementation:
    // const errorContent = error || (reserveErrorSpace ? "\u00A0" : null);
    // <p className={`mt-1 text-sm ${error ? "text-red-500" : "invisible"}`}>

    const errorMsg = document.querySelector("p");
    expect(errorMsg).toBeInTheDocument();
    expect(errorMsg).toHaveClass("invisible");
    expect(errorMsg?.textContent).toBe("\u00A0");
  });

  it("forward refs", () => {
    let capturedRef: HTMLInputElement | null = null;
    const TestWrapper = () => {
      const ref = React.useRef<HTMLInputElement>(null);
      React.useEffect(() => {
        capturedRef = ref.current;
      }, []);
      return <Input ref={ref} />;
    };
    render(<TestWrapper />);
    expect(capturedRef).toBeInstanceOf(HTMLInputElement);
  });

  it("renders correct input attributes", () => {
    render(<Input placeholder="Enter text" type="password" />);
    const input = screen.getByPlaceholderText("Enter text");
    expect(input).toHaveAttribute("type", "password");
  });

  it("renders required asterisk", () => {
    render(<Input label="Required Field" required id="req" />);
    // Label text should contain the asterisk
    expect(screen.getByText("Required Field*")).toBeInTheDocument();
  });
});
