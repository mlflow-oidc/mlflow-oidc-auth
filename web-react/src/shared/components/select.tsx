import React from "react";

interface Option {
  label: string;
  value: string;
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: (string | Option)[];
  containerClassName?: string;
  ref?: React.Ref<HTMLSelectElement>;
  reserveErrorSpace?: boolean;
}

export const Select = ({
  label,
  error,
  options,
  className = "",
  containerClassName = "",
  id,
  ref,
  reserveErrorSpace = false,
  ...props
}: SelectProps) => {
  const errorContent = error || (reserveErrorSpace ? "\u00A0" : null);

  return (
    <div className={containerClassName}>
      {label && (
        <label
          htmlFor={id}
          className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1"
        >
          {label}
          {props.required && "*"}
        </label>
      )}
      <select
        ref={ref}
        id={id}
        className={`w-full px-3 py-2 border rounded-md focus:outline-none
            text-ui-text dark:text-ui-text-dark
            bg-ui-bg dark:bg-ui-bg-dark
            border-ui-border dark:border-ui-border-dark
            focus:border-btn-primary dark:focus:border-btn-primary-dark
            transition duration-150 ease-in-out cursor-pointer
            disabled:opacity-70 disabled:cursor-not-allowed
            custom-select
            ${error ? "border-red-500 focus:border-red-500 dark:border-red-500 dark:focus:border-red-500" : ""}
            ${className}`}
        {...props}
      >
        {options.map((option) => {
          const optLabel = typeof option === "string" ? option : option.label;
          const optValue = typeof option === "string" ? option : option.value;
          return (
            <option key={optValue} value={optValue}>
              {optLabel}
            </option>
          );
        })}
      </select>
      {errorContent && (
        <p className={`mt-1 text-sm ${error ? "text-red-500" : "invisible"}`}>
          {errorContent}
        </p>
      )}
    </div>
  );
};

Select.displayName = "Select";
