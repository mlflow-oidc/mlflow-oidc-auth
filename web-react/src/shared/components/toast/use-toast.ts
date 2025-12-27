import { use } from "react";
import { ToastContext } from "./toast-context-val";

export const useToast = () => {
  const context = use(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
};
