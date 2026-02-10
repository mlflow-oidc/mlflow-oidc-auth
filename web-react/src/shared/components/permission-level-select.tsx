import React from "react";
import { Select } from "./select";
import type { PermissionLevel } from "../types/entity";

const PERMISSION_LEVELS: PermissionLevel[] = [
  "READ",
  "EDIT",
  "MANAGE",
  "NO_PERMISSIONS",
];

interface PermissionLevelSelectProps {
  value: PermissionLevel;
  onChange: (value: PermissionLevel) => void;
  id?: string;
  label?: string;
  disabled?: boolean;
  required?: boolean;
  className?: string;
  containerClassName?: string;
}

export const PermissionLevelSelect: React.FC<PermissionLevelSelectProps> = ({
  value,
  onChange,
  id = "permission-level",
  label = "Permissions*",
  disabled = false,
  required = true,
  className,
  containerClassName,
}) => {
  return (
    <Select
      id={id}
      label={label}
      value={value}
      onChange={(e) => onChange(e.target.value as PermissionLevel)}
      required={required}
      disabled={disabled}
      options={PERMISSION_LEVELS.map((level) => ({
        label: level,
        value: level,
      }))}
      className={className}
      containerClassName={containerClassName}
    />
  );
};
