import React, { useEffect } from "react";
import type { ToastMessage } from "./toast-types";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import {
  faCheckCircle,
  faExclamationCircle,
  faInfoCircle,
  faExclamationTriangle,
  faXmark,
} from "@fortawesome/free-solid-svg-icons";

interface ToastProps extends ToastMessage {
  onClose: () => void;
}

export const Toast: React.FC<ToastProps> = ({
  message,
  type,
  duration,
  onClose,
}) => {
  useEffect(() => {
    if (duration) {
      const timer = setTimeout(onClose, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  const styles = {
    success:
      "bg-green-100 dark:bg-green-900 border-green-200 dark:border-green-800 text-green-800 dark:text-green-100",
    error:
      "bg-red-100 dark:bg-red-900 border-red-200 dark:border-red-800 text-red-800 dark:text-red-100",
    info: "bg-blue-100 dark:bg-blue-900 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-100",
    warning:
      "bg-yellow-100 dark:bg-yellow-900 border-yellow-200 dark:border-yellow-800 text-yellow-800 dark:text-yellow-100",
  };

  const icons = {
    success: faCheckCircle,
    error: faExclamationCircle,
    info: faInfoCircle,
    warning: faExclamationTriangle,
  };

  return (
    <div
      className={`
        pointer-events-auto flex items-start p-4 rounded shadow-lg border w-80
        transition-all duration-300 ease-in-out transform translate-x-0 opacity-100
        ${styles[type]}
      `}
      role="alert"
    >
      <div className="shrink-0 mr-3 mt-0.5">
        <FontAwesomeIcon icon={icons[type]} className="h-4 w-4" />
      </div>
      <div className="flex-1 text-sm font-medium wrap-break-word">
        {message}
      </div>
      <button
        type="button"
        onClick={onClose}
        className="ml-3 shrink-0 text-current opacity-70 hover:opacity-100 transition-opacity cursor-pointer"
        aria-label="Close"
      >
        <FontAwesomeIcon icon={faXmark} className="h-4 w-4" />
      </button>
    </div>
  );
};
