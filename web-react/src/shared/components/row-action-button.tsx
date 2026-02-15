import React from "react";
import { useNavigate } from "react-router";
import { faLock } from "@fortawesome/free-solid-svg-icons";
import { Button } from "./button";
import { encodeRouteParam } from "../../shared/utils/string-utils";

interface RowActionButtonProps {
  entityId: string;
  route: string;
  buttonText: string;
  suffix?: string;
}

export function RowActionButton({
  entityId,
  route,
  buttonText,
  suffix = "",
}: RowActionButtonProps) {
  const navigate = useNavigate();
  const normalizedRoute = route.replace(/^\/+/, "");
  const targetRoute = `/${normalizedRoute}/${encodeRouteParam(
    entityId,
  )}${suffix}`;

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
