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
  const ref = React.useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (isOpen) {
      ref.current?.showModal();
      document.body.style.overflow = "hidden";
    } else {
      ref.current?.close();
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  return (
    <dialog
      ref={ref}
      className={`relative m-auto bg-ui-bg dark:bg-ui-secondary-bg-dark rounded-lg shadow-xl w-full ${width} p-6 backdrop:bg-ui-bg-dark/50 dark:backdrop:bg-ui-bg-dark/70`}
      onClick={(e) => {
        if (e.target === ref.current) {
          onClose();
        }
      }}
      onCancel={(e) => {
        // Escape: let the parent decide. Closing natively here would hide the dialog while the
        // parent still thinks it is open — and a parent busy saving keeps it open on purpose.
        e.preventDefault();
        // React passes `cancel` up its component tree although the native event does not bubble,
        // so a dialog opened inside this one would close both. Answer only for this dialog.
        if (e.target !== e.currentTarget) return;
        onClose();
      }}
    >
      <div className="absolute top-1 right-1">
        <Button
          onClick={onClose}
          aria-label="Close modal"
          variant="ghost"
          icon={faXmark}
        />
      </div>

      <div className="mb-4">
        <h4 className="text-lg text-ui-text dark:text-ui-text-dark font-semibold">
          {title}
        </h4>
      </div>

      <div className="space-y-5">{children}</div>
    </dialog>
  );
};
