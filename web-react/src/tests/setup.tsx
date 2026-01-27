import "@testing-library/jest-dom";
import { vi, beforeAll } from "vitest";

// JSDOM doesn't support <dialog> yet
beforeAll(() => {
  if (typeof window !== "undefined") {
    HTMLDialogElement.prototype.showModal = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.open = true;
    });
    HTMLDialogElement.prototype.close = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.open = false;
    });
  }
});

