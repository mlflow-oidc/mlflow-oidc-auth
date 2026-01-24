import React from "react";

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  containerClassName?: string;
  children?: React.ReactNode;
  ref?: React.Ref<HTMLInputElement>;
  reserveErrorSpace?: boolean;
}

export const Input = ({
  label,
  error,
  className = "",
  containerClassName = "",
  id,
  children,
  ref,
  reserveErrorSpace = false,
  ...props
}: InputProps) => {
  const errorContent = error || (reserveErrorSpace ? "\u00A0" : null);

  return (
    <div className={`${containerClassName} relative`}>
      {label && (
        <label
          htmlFor={id}
          className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1"
        >
          {label}
          {props.required && "*"}
        </label>
      )}
      <input
        ref={ref}
        id={id}
        className={`w-full px-3 py-2 border rounded-md focus:outline-none
            text-ui-text dark:text-ui-text-dark
            bg-ui-bg dark:bg-ui-bg-dark
            border-ui-border dark:border-ui-border-dark
            focus:border-btn-primary dark:focus:border-btn-primary-dark
            transition duration-150 ease-in-out
            disabled:opacity-70 disabled:cursor-not-allowed
            read-only:cursor-default read-only:focus:border-ui-secondary-bg dark:read-only:focus:border-ui-secondary-bg-dark
            ${error ? "border-red-500 focus:border-red-500 dark:border-red-500 dark:focus:border-red-500" : ""}
            ${className}`}
        {...props}
      />
      {children}
      {errorContent && (
        <p className={`mt-1 text-sm ${error ? "text-red-500" : "invisible"}`}>
          {errorContent}
        </p>
      )}
    </div>
  );
};

Input.displayName = "Input";
