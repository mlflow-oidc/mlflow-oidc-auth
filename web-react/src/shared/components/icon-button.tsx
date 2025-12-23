import React from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import type { IconDefinition } from "@fortawesome/free-solid-svg-icons";

interface IconButtonProps {
    icon: IconDefinition;
    onClick: (e: React.MouseEvent) => void;
    title?: string;
}

export function IconButton({ icon, onClick, title }: IconButtonProps) {
    const handleClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        onClick(e);
    };

    return (
        <button
            type="button"
            onClick={handleClick}
            title={title}
            className="p-1 border rounded text-xs flex items-center justify-center
                bg-btn-secondary dark:bg-btn-secondary-dark
                hover:bg-btn-secondary-hover dark:hover:bg-btn-secondary-hover-dark
                text-btn-primary dark:text-btn-primary-dark
                hover:text-btn-primary-hover dark:hover:text-btn-primary-hover-dark
                border-btn-secondary dark:border-btn-secondary-dark
                hover:border-btn-secondary-border-hover dark:hover:border-btn-secondary-border-hover-dark
                transition-all duration-50 ease-in-out cursor-pointer
                w-8 h-8"
        >
            <FontAwesomeIcon icon={icon} className="text-sm" />
        </button>
    );
}
