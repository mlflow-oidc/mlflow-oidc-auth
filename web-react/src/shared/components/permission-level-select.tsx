import React from "react";
import { Select } from "./select";
import type { PermissionLevel, PermissionType } from "../types/entity";

const DEFAULT_PERMISSION_LEVELS: PermissionLevel[] = [
  "READ",
  "EDIT",
  "MANAGE",
  "NO_PERMISSIONS",
];

const AI_GATEWAY_PERMISSION_LEVELS: PermissionLevel[] = [
  "READ",
  "USE",
  "EDIT",
  "MANAGE",
  "NO_PERMISSIONS",
];

interface PermissionLevelSelectProps {
  value: PermissionLevel;
  onChange: (value: PermissionLevel) => void;
  type?: PermissionType;
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
  type,
  id = "permission-level",
  label = "Permissions*",
  disabled = false,
  required = true,
  className,
  containerClassName,
}) => {
  const levels =
    type === "ai-endpoints" || type === "ai-secrets" || type === "ai-models"
      ? AI_GATEWAY_PERMISSION_LEVELS
      : DEFAULT_PERMISSION_LEVELS;

  return (
    <Select
      id={id}
      label={label}
      value={value}
      onChange={(e) => onChange(e.target.value as PermissionLevel)}
      required={required}
      disabled={disabled}
      options={levels.map((level) => ({
        label: level,
        value: level,
      }))}
      className={className}
      containerClassName={containerClassName}
    />
  );
};
