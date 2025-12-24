import React from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import type { IconDefinition } from "@fortawesome/free-solid-svg-icons";

export type ButtonVariant = "action" | "ghost" | "primary";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: ButtonVariant;
    icon?: IconDefinition;
    iconClassName?: string;
}

export function Button({
    variant = "action",
    icon,
    iconClassName = "text-sm",
    children,
    className = "",
    ...props
}: ButtonProps) {
    const baseClasses = "flex items-center justify-center transition-all duration-50 ease-in-out cursor-pointer rounded";

    const variantClasses = {
        primary: `
      px-4 py-2 font-medium shadow-md
      bg-btn-primary dark:bg-btn-primary-dark
      text-btn-primary-text dark:text-btn-primary-text-dark
      hover:bg-btn-primary-hover dark:hover:bg-btn-primary-hover-dark
    `,
        action: `
      p-1 border text-xs
      bg-btn-secondary dark:bg-btn-secondary-dark
      hover:bg-btn-secondary-hover dark:hover:bg-btn-secondary-hover-dark
      text-btn-primary dark:text-btn-primary-dark
      hover:text-btn-primary-hover dark:hover:text-btn-primary-hover-dark
      border-btn-secondary dark:border-btn-secondary-dark
      hover:border-btn-secondary-border-hover dark:hover:border-btn-secondary-border-hover-dark
    `,
        ghost: `
      p-1 px-2 py-2
      text-text-primary dark:text-text-primary-dark
      hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark
      hover:bg-bg-primary-hover dark:hover:bg-bg-primary-hover-dark
    `,
    };

    const combinedClasses = `${baseClasses} ${variantClasses[variant]} ${className}`.replace(/\s+/g, " ").trim();

    return (
        <button type="button" className={combinedClasses} {...props}>
            {icon && <FontAwesomeIcon icon={icon} className={iconClassName} />}
            {children && <span className={icon ? "ml-1" : ""}>{children}</span>}
        </button>
    );
}
