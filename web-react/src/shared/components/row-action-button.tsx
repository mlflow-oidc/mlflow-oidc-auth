import React from "react";
import { useNavigate } from "react-router";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faLock } from "@fortawesome/free-solid-svg-icons";
import { useRuntimeConfig } from "../context/use-runtime-config";

interface RowActionButtonProps {
  entityId: string;
  route: string;
  buttonText: string;
}

export function RowActionButton({
  entityId,
  route,
  buttonText,
}: RowActionButtonProps) {
  const navigate = useNavigate();
  const basePath = useRuntimeConfig().basePath;
  const targetRoute = `${basePath}/${route}/${entityId}`;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    void navigate(targetRoute);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className="p-1 border rounded text-xs flex items-center gap-1
                bg-btn-secondary dark:bg-btn-secondary-dark
                hover:bg-btn-secondary-hover dark:hover:bg-btn-secondary-hover-dark
                text-btn-primary dark:text-btn-primary-dark
                hover:text-btn-primary-hover dark:hover:text-btn-primary-hover-dark
                border-btn-secondary dark:border-btn-secondary-dark
                hover:border-transparent
                 transition-all duration-50 ease-in-out cursor-pointer"
    >
      <FontAwesomeIcon icon={faLock} className="text-sm" />
      <span>{buttonText}</span>
    </button>
  );
}
