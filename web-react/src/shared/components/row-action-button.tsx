import React from "react";
import { useNavigate } from "react-router";
import { faLock } from "@fortawesome/free-solid-svg-icons";
import { Button } from "./button";

interface RowActionButtonProps {
  entityId: string;
  route: string;
  buttonText: string;
}

export function RowActionButton({
  entityId,
  route,
  buttonText,
}: RowActionButtonProps) {
  const navigate = useNavigate();
  const normalizedRoute = route.replace(/^\/+/, "");
  const targetRoute = `/${normalizedRoute}/${encodeURIComponent(entityId)}`;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    void navigate(targetRoute);
  };

  return (
    <Button onClick={handleClick} icon={faLock} className="gap-1">
      {buttonText}
    </Button>
  );
}
