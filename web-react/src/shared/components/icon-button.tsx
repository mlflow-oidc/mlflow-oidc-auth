import React from "react";
import type { IconDefinition } from "@fortawesome/free-solid-svg-icons";
import { Button } from "./button";

interface IconButtonProps {
  icon: IconDefinition;
  onClick: (e: React.MouseEvent) => void;
  title?: string;
  disabled?: boolean;
}

export function IconButton({
  icon,
  onClick,
  title,
  disabled,
}: IconButtonProps) {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!disabled) {
      onClick(e);
    }
  };

  return (
    <Button
      onClick={handleClick}
      title={title}
      icon={icon}
      className="w-7 h-7"
      disabled={disabled}
    />
  );
}
