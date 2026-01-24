import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { ToastProvider } from "./toast-context";
import { useToast } from "./use-toast";

const TestComponent = () => {
  const { showToast } = useToast();
  return (
    <button onClick={() => showToast("Test message", "success", 1000)}>
      Show Toast
    </button>
  );
};

describe("ToastProvider", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("renders children and shows toast on call", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    const button = screen.getByText("Show Toast");
    fireEvent.click(button);

    expect(screen.getByText("Test message")).toBeDefined();
    expect(screen.getByRole("alert")).toBeDefined();
  });

  it("removes toast after duration", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByText("Show Toast"));
    expect(screen.getByText("Test message")).toBeDefined();

    act(() => {
      vi.advanceTimersByTime(1100);
    });

    expect(screen.queryByText("Test message")).toBeNull();
  });

  it("removes toast when closed manually", () => {
    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByText("Show Toast"));
    const closeButton = screen.getByLabelText("Close");
    fireEvent.click(closeButton);

    expect(screen.queryByText("Test message")).toBeNull();
  });
});
