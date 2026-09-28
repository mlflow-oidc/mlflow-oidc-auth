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

  describe("modal dialogs (toasts stay usable while one is open)", () => {
    const openDialog = (): HTMLDialogElement => {
      const dialog = document.createElement("dialog");
      document.body.appendChild(dialog);
      dialog.showModal(); // stubbed in tests/setup.tsx to set `open`
      return dialog;
    };

    beforeEach(() => {
      vi.useRealTimers();
    });

    afterEach(() => {
      document.querySelectorAll("dialog").forEach((d) => d.remove());
      vi.useRealTimers();
    });

    it("renders a toast outside any dialog when none is open", () => {
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      const alert = screen.getByRole("alert");
      expect(alert.closest("dialog")).toBeNull();
      expect(screen.getByTestId("toast-container").parentElement).toBe(
        document.body,
      );
    });

    it("renders a toast raised while a modal is open inside it, and its close button works", () => {
      const dialog = openDialog();
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));

      const alert = screen.getByRole("alert");
      expect(dialog).toContainElement(alert);
      fireEvent.click(screen.getByLabelText("Close"));
      expect(screen.queryByRole("alert")).toBeNull();
    });

    it("uses the last open dialog when several are open", () => {
      openDialog();
      const top = openDialog();
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      expect(top).toContainElement(screen.getByRole("alert"));
    });

    it("moves a visible toast into a dialog that opens and back out when it closes, without duplicating it", async () => {
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      const alert = screen.getByRole("alert");

      const dialog = openDialog();
      await waitFor(() => expect(dialog).toContainElement(alert));
      expect(screen.getAllByRole("alert")).toHaveLength(1);

      dialog.close();
      await waitFor(() => expect(alert.closest("dialog")).toBeNull());
      expect(screen.getAllByRole("alert")).toHaveLength(1);
      // Same node: moved, not remounted.
      expect(screen.getByRole("alert")).toBe(alert);
    });

    it("moves a toast back out when its dialog is removed from the DOM while open", async () => {
      const dialog = openDialog();
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      expect(dialog).toContainElement(screen.getByRole("alert"));

      dialog.remove();
      await waitFor(() =>
        expect(screen.getByTestId("toast-container").parentElement).toBe(
          document.body,
        ),
      );
      expect(screen.getByRole("alert")).toHaveTextContent("Test message");
    });

    it("keeps the auto-dismiss timer running across a move into a dialog", async () => {
      vi.useFakeTimers();
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      act(() => {
        vi.advanceTimersByTime(600);
      });

      const dialog = openDialog();
      // MutationObserver callbacks run as microtasks.
      await act(async () => {
        await Promise.resolve();
      });
      expect(dialog).toContainElement(screen.getByRole("alert"));

      // 600ms + 500ms > 1000ms: dismissed on the original schedule, not restarted by the move.
      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(screen.queryByRole("alert")).toBeNull();
    });

    it("does not restart earlier toasts' timers when another toast arrives", () => {
      vi.useFakeTimers();
      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      fireEvent.click(screen.getByText("Show Toast"));
      act(() => {
        vi.advanceTimersByTime(600);
      });
      fireEvent.click(screen.getByText("Show Toast"));
      expect(screen.getAllByRole("alert")).toHaveLength(2);
      act(() => {
        vi.advanceTimersByTime(500);
      });
      expect(screen.getAllByRole("alert")).toHaveLength(1);
    });

    it("removes the container and stops observing on unmount", () => {
      const observe = vi.spyOn(MutationObserver.prototype, "observe");
      const disconnect = vi.spyOn(MutationObserver.prototype, "disconnect");
      const { unmount } = render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>,
      );
      expect(observe).not.toHaveBeenCalled(); // no observer without toasts
      fireEvent.click(screen.getByText("Show Toast"));
      expect(observe).toHaveBeenCalledTimes(1);

      const container = screen.getByTestId("toast-container");
      unmount();
      expect(disconnect).toHaveBeenCalled();
      expect(container.isConnected).toBe(false);
      expect(document.querySelector('[data-testid="toast-container"]')).toBeNull();
      observe.mockRestore();
      disconnect.mockRestore();
    });
  });
});
