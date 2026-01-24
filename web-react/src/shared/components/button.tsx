import React from "react";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import type { IconDefinition } from "@fortawesome/free-solid-svg-icons";

export type ButtonVariant =
  | "action"
  | "danger"
  | "ghost"
  | "primary"
  | "secondary";

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
  disabled,
  type = "button",
  ...props
}: ButtonProps) {
  const baseClasses =
    "flex items-center justify-center transition-all duration-50 ease-in-out rounded font-medium";
  const cursorClass = disabled
    ? "cursor-not-allowed opacity-50"
    : "cursor-pointer";

  const variantClasses = {
    primary: `
      px-3 py-1.5 text-sm shadow-md
      bg-btn-primary dark:bg-btn-primary-dark
      text-btn-primary-text dark:text-btn-primary-text-dark
      hover:bg-btn-primary-hover dark:hover:bg-btn-primary-hover-dark
  `,
    secondary: `
      px-3 py-1.5 text-sm border
      bg-btn-secondary dark:bg-btn-secondary-dark
      text-btn-secondary-text dark:text-btn-secondary-text-dark
      border-btn-secondary-border dark:border-btn-secondary-border-dark
      hover:bg-btn-secondary-hover dark:hover:bg-btn-secondary-hover-dark
      hover:text-btn-secondary-text-hover dark:hover:text-btn-secondary-text-hover-dark
      hover:border-btn-secondary-border-hover dark:hover:border-btn-secondary-border-hover-dark
      active:bg-btn-secondary-active dark:active:bg-btn-secondary-active-dark
      active:text-btn-secondary-text-active dark:active:text-btn-secondary-text-active-dark
      active:border-btn-secondary-border-active dark:active:border-btn-secondary-border-active-dark
      transition-all duration-200
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
    danger: `
      px-3 py-1.5 text-sm border bg-transparent
      text-btn-danger-outline border-btn-danger-outline-border
      hover:bg-btn-danger-outline-hover-bg
      hover:text-btn-danger-outline-hover-text
      hover:border-btn-danger-outline-hover-border

      dark:text-btn-danger-outline-dark
      dark:border-btn-danger-outline-border-dark
      dark:hover:bg-btn-danger-outline-hover-bg-dark
      dark:hover:text-btn-danger-outline-hover-text-dark
      dark:hover:border-btn-danger-outline-hover-border-dark

      disabled:bg-btn-disabled-bg disabled:text-btn-disabled-text
      disabled:border-transparent disabled:opacity-100

      dark:disabled:bg-btn-disabled-bg-dark
      dark:disabled:text-btn-disabled-text-dark
      dark:disabled:border-transparent
  `,
  };

  const combinedClasses =
    `${baseClasses} ${cursorClass} ${variantClasses[variant]} ${className}`
      .replace(/\s+/g, " ")
      .trim();

  return (
    <button
      type={type}
      className={combinedClasses}
      disabled={disabled}
      {...props}
    >
      {icon && <FontAwesomeIcon icon={icon} className={iconClassName} />}
      {children && <span className={icon ? "ml-1" : ""}>{children}</span>}
    </button>
  );
}
