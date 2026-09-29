import React from "react";
import type { IconDefinition } from "@fortawesome/free-solid-svg-icons";
import { Button } from "./button";

interface IconButtonProps {
  icon: IconDefinition;
  onClick: (e: React.MouseEvent) => void;
  title?: string;
  disabled?: boolean;
  /**
   * Low-emphasis style for secondary row actions in list tables: muted
   * colour by default, full colour on row hover, button hover and keyboard
   * focus. Defaults to false (unchanged appearance).
   */
  muted?: boolean;
}

export function IconButton({
  icon,
  onClick,
  title,
  disabled,
  muted = false,
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
      variant={muted ? "muted" : "action"}
      className="w-7 h-7"
      disabled={disabled}
    />
  );
}
