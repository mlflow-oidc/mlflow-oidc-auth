import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  act,
  fireEvent,
  waitFor,
} from "@testing-library/react";
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

  describe("top layer (toasts above a modal dialog's backdrop)", () => {
    const proto = HTMLElement.prototype as unknown as Record<string, unknown>;
    let showPopover: ReturnType<typeof vi.fn>;
    let hidePopover: ReturnType<typeof vi.fn>;

    beforeEach(() => {
      vi.useRealTimers();
      showPopover = vi.fn();
      hidePopover = vi.fn();
      proto.showPopover = showPopover;
      proto.hidePopover = hidePopover;
    });

    afterEach(() => {
      delete proto.showPopover;
      delete proto.hidePopover;
      document.querySelectorAll("dialog").forEach((d) => d.remove());
    });

    it("renders the container as a manual popover and shows it with the first toast", () => {
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      const container = screen.getByTestId("toast-container");
      expect(container).toHaveAttribute("popover", "manual");
      expect(showPopover).not.toHaveBeenCalled();

      fireEvent.click(screen.getByText("Show Toast"));
      expect(showPopover).toHaveBeenCalledTimes(1);
      expect(showPopover.mock.contexts[0]).toBe(container);
    });

    it("re-raises above a dialog opened while a toast is visible", async () => {
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      expect(showPopover).toHaveBeenCalledTimes(1);

      const dialog = document.createElement("dialog");
      document.body.appendChild(dialog);
      dialog.setAttribute("open", "");

      await waitFor(() => expect(showPopover).toHaveBeenCalledTimes(2));
      // Re-raising means leaving the top layer and re-entering it on top.
      expect(hidePopover).toHaveBeenCalled();
    });

    it("re-raises for each new toast and hides once all are gone", () => {
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      fireEvent.click(screen.getByText("Show Toast"));
      expect(showPopover).toHaveBeenCalledTimes(2);

      hidePopover.mockClear();
      screen.getAllByLabelText("Close").forEach((b) => fireEvent.click(b));
      expect(screen.queryByRole("alert")).toBeNull();
      expect(hidePopover).toHaveBeenCalled();
    });

    it("auto-dismisses and stays announced (role=alert) while a dialog is open", () => {
      vi.useFakeTimers();
      const dialog = document.createElement("dialog");
      document.body.appendChild(dialog);
      dialog.setAttribute("open", "");
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      const container = screen.getByTestId("toast-container");
      expect(container).toHaveAttribute("popover", "manual");
      // `hidden`: the showPopover stub never makes jsdom treat the popover as open.
      const alert = screen.getByRole("alert", { hidden: true });
      expect(alert).toHaveTextContent("Test message");
      expect(container).toContainElement(alert);

      act(() => {
        vi.advanceTimersByTime(1100);
      });
      expect(screen.queryByRole("alert", { hidden: true })).toBeNull();
      expect(hidePopover).toHaveBeenCalled();
      vi.useRealTimers();
    });

    it("leaves the container a plain element without Popover API support", () => {
      delete proto.showPopover;
      delete proto.hidePopover;
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      expect(screen.getByTestId("toast-container")).not.toHaveAttribute(
        "popover",
      );
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });
});
