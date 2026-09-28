import type { ReactNode } from "react";
import React, {
  useState,
  useCallback,
  useMemo,
  useRef,
  useLayoutEffect,
} from "react";
import { createPortal } from "react-dom";
import type { ToastMessage, ToastType } from "./toast-types";
import { ToastContext } from "./toast-context-val";
import { Toast } from "./toast";

/** Whether `dialog` is modal (opened with `showModal()`); false where `:modal` is unsupported. */
function isModal(dialog: HTMLDialogElement): boolean {
  try {
    return dialog.matches(":modal");
  } catch {
    return false;
  }
}

/**
 * The dialog toasts must live in to stay usable, or `null` when none is open.
 *
 * A modal `<dialog>` makes everything outside itself inert: a toast rendered elsewhere is not
 * clickable and may not be announced. Prefer the last open modal dialog (the top-most one in
 * practice); where `:modal` is unsupported, fall back to the last `dialog[open]`.
 */
function findTopDialog(): HTMLDialogElement | null {
  const open = Array.from(
    document.querySelectorAll<HTMLDialogElement>("dialog[open]"),
  );
  const modal = open.filter(isModal);
  const candidates = modal.length > 0 ? modal : open;
  return candidates.length > 0 ? candidates[candidates.length - 1] : null;
}

/**
 * Put the toast host inside the top-most open dialog, or back on `document.body`.
 *
 * The host is a single long-lived element moved in the DOM rather than a portal whose target
 * changes: React keeps the toasts mounted, so none is lost or duplicated and their auto-dismiss
 * timers keep running. Its `position: fixed` resolves against the viewport inside a dialog too
 * (the shared modal sets no transform, filter or containment), so it is not clipped by the
 * dialog's own box or overflow.
 */
function placeHost(host: HTMLElement): void {
  const parent = findTopDialog() ?? document.body;
  if (host.parentNode !== parent) parent.appendChild(host);
}

const HOST_CLASS =
  "fixed bottom-6 right-1/2 translate-x-1/2 z-100 flex flex-col space-y-2 pointer-events-none items-center";

export const ToastProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [host] = useState(() => {
    const el = document.createElement("div");
    el.className = HOST_CLASS;
    el.dataset.testid = "toast-container";
    return el;
  });
  const nextId = useRef(0);

  const showToast = useCallback(
    (message: string, type: ToastType, duration = 3000) => {
      nextId.current += 1;
      const id = `${Date.now()}-${nextId.current}`;
      setToasts((prev) => [...prev, { id, message, type, duration }]);
    },
    [],
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const contextValue = useMemo(
    () => ({ showToast, removeToast }),
    [showToast, removeToast],
  );

  const hasToasts = toasts.length > 0;

  // Attach the host for the provider's lifetime; remove it on unmount.
  useLayoutEffect(() => {
    placeHost(host);
    return () => host.remove();
  }, [host]);

  // While toasts are visible, follow dialogs opening, closing, or being removed from the DOM.
  useLayoutEffect(() => {
    if (!hasToasts) return;
    placeHost(host);
    if (typeof MutationObserver === "undefined") return;
    const observer = new MutationObserver(() => placeHost(host));
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["open"],
      childList: true,
      subtree: true,
    });
    return () => observer.disconnect();
  }, [hasToasts, host]);

  return (
    <ToastContext value={contextValue}>
      {children}
      {createPortal(
        toasts.map((toast) => (
          <Toast
            key={toast.id}
            {...toast}
            onClose={() => removeToast(toast.id)}
          />
        )),
        host,
      )}
    </ToastContext>
  );
};
