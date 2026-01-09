import React, { useEffect } from "react";
import { Button } from "./button";
import { faXmark } from "@fortawesome/free-solid-svg-icons";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  width?: string;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  width = "max-w-xl",
}) => {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
    }

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto bg-ui-bg-dark/50 dark:bg-ui-bg-dark/70 transition-opacity flex justify-center items-start pt-16 sm:pt-24 md:items-center md:pt-0"
      onClick={onClose}
    >
      <div
        className={`relative bg-ui-bg dark:bg-ui-secondary-bg-dark rounded-lg shadow-xl w-full ${width} p-6`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="absolute top-0.5 right-1">
          <Button
            onClick={onClose}
            aria-label="Close modal"
            variant="ghost"
            icon={faXmark}
          />
        </div>

        <div className="mb-6">
          <h4 className="text-xl text-ui-text dark:text-ui-text-dark font-semibold">
            {title}
          </h4>
        </div>

        <div className="space-y-5">
          {children}
        </div>
      </div>
    </div>
  );
};
