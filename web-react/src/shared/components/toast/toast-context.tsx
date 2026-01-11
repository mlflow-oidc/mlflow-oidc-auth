import type { ReactNode } from "react";
import React, { useState, useCallback, useMemo } from "react";
import type { ToastMessage, ToastType } from "./toast-types";
import { ToastContext } from "./toast-context-val";
import { Toast } from "./toast";

export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const showToast = useCallback(
    (message: string, type: ToastType, duration = 3000) => {
      const id = Date.now().toString();
      setToasts((prev) => [...prev, { id, message, type, duration }]);
    },
    []
  );

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const contextValue = useMemo(() => ({ showToast, removeToast }), [showToast, removeToast]);

  return (
    <ToastContext value={contextValue}>
      {children}
      <div className="fixed bottom-6 right-1/2 translate-x-1/2 z-[100] flex flex-col space-y-2 pointer-events-none items-center">
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
