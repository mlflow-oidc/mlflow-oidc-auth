import React from "react";

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  className?: string;
  labelClassName?: string;
  disabled?: boolean;
}

export const Switch: React.FC<SwitchProps> = ({
  checked,
  onChange,
  label,
  className = "",
  labelClassName = "",
  disabled = false,
}) => {
  return (
    <div
      className={`flex items-center gap-2 ${
        disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
      } ${className}`}
      onClick={() => !disabled && onChange(!checked)}
    >
      <div
        role="switch"
        aria-checked={checked}
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => {
          if (!disabled && (e.key === "Enter" || e.key === " ")) {
            e.preventDefault();
            onChange(!checked);
          }
        }}
        className={`w-[55px] h-[26px] rounded-full relative transition-colors duration-200 ease-in-out border border-transparent ${
          checked
            ? "bg-btn-primary dark:bg-btn-primary-dark"
            : "bg-gray-200 dark:bg-gray-700"
        }`}
      >
        <span
          className={`absolute left-1.5 top-1/2 -translate-y-1/2 text-[10px] font-bold text-btn-primary-text dark:text-btn-primary-text-dark transition-opacity duration-200 pointer-events-none ${
            checked ? "opacity-100" : "opacity-0"
          }`}
        >
          ON
        </span>
        <span
          className={`absolute right-1.5 top-1/2 -translate-y-1/2 text-[10px] font-bold text-gray-500 dark:text-gray-300 transition-opacity duration-200 pointer-events-none ${
            checked ? "opacity-0" : "opacity-100"
          }`}
        >
          OFF
        </span>
        <div
          className={`absolute top-[2px] left-[2px] w-5 h-5 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out z-10 ${
            checked ? "translate-x-[29px]" : "translate-x-0"
          }`}
        />
      </div>
      {label && (
        <span className={`text-sm font-medium select-none ${!labelClassName ? "text-btn-primary-text dark:text-btn-primary-text-dark" : ""} ${labelClassName}`}>
          {label}
        </span>
      )}
    </div>
  );
};
