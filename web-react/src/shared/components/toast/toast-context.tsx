import type { ReactNode } from "react";
import React, {
  useState,
  useCallback,
  useMemo,
  useRef,
  useLayoutEffect,
  useEffect,
} from "react";
import type { ToastMessage, ToastType } from "./toast-types";
import { ToastContext } from "./toast-context-val";
import { Toast } from "./toast";

/**
 * Move the toast container to the top of the browser's top layer.
 *
 * A modal `<dialog>` opened with `showModal()` renders in the top layer, above every z-index, so
 * an ordinary fixed-position toast ends up under its backdrop. A `popover="manual"` element is
 * also in the top layer, and the top layer paints in the order elements entered it: hiding and
 * re-showing the popover puts the toasts back above whatever dialog opened last.
 *
 * Without Popover API support (older browsers, jsdom) this is a no-op and the container keeps
 * its plain fixed positioning and z-index.
 */
function raiseToTopLayer(el: HTMLElement): void {
  if (typeof el.showPopover !== "function") return;
  try {
    el.hidePopover();
  } catch {
    // Not currently showing.
  }
  try {
    el.showPopover();
  } catch {
    // Disconnected or unsupported; the fixed-position fallback still applies.
  }
}

/** Whether this browser has the Popover API. Checked per render so tests can stub it. */
function supportsPopover(): boolean {
  return (
    typeof HTMLElement !== "undefined" &&
    typeof HTMLElement.prototype.showPopover === "function"
  );
}

function lowerFromTopLayer(el: HTMLElement): void {
  if (typeof el.hidePopover !== "function") return;
  try {
    el.hidePopover();
  } catch {
    // Already hidden.
  }
}

export const ToastProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
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

  // Re-raise on every new toast, so it lands above a dialog that opened since the last one.
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    if (hasToasts) {
      raiseToTopLayer(el);
    } else {
      lowerFromTopLayer(el);
    }
  }, [toasts, hasToasts]);

  // A dialog opened while toasts are on screen would cover them: raise again when one opens.
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !hasToasts || typeof MutationObserver === "undefined") return;
    const observer = new MutationObserver((mutations) => {
      const dialogOpened = mutations.some(
        (m) => m.target instanceof HTMLDialogElement && m.target.open,
      );
      if (dialogOpened) raiseToTopLayer(el);
    });
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["open"],
      subtree: true,
    });
    return () => observer.disconnect();
  }, [hasToasts]);

  return (
    <ToastContext value={contextValue}>
      {children}
      <div
        ref={containerRef}
        // Only where the API exists: elsewhere (jsdom, older browsers) an inert `popover`
        // attribute would hide the container from the accessibility tree.
        popover={supportsPopover() ? "manual" : undefined}
        data-testid="toast-container"
        className="fixed top-auto left-auto bottom-6 right-1/2 translate-x-1/2 z-100 m-0 p-0 border-0 bg-transparent overflow-visible flex flex-col space-y-2 pointer-events-none items-center"
      >
        {toasts.map((toast) => (
          <Toast
            key={toast.id}
            {...toast}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </ToastContext>
  );
};
