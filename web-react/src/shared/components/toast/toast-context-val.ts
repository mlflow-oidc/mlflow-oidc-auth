import { createContext } from "react";
import type { ToastType } from "./toast-types";

export interface ToastContextType {
  showToast: (message: string, type: ToastType, duration?: number) => void;
  removeToast: (id: string) => void;
}

export const ToastContext = createContext<ToastContextType | undefined>(undefined);
