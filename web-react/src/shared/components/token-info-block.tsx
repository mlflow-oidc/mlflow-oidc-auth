import React from "react";
import { CreateAccessTokenButton } from "../../core/components/create-access-token-button";

interface TokenInfoBlockProps {
  username: string;
  passwordExpiration?: string | null;
  onTokenGenerated?: () => void;
}

export const TokenInfoBlock: React.FC<TokenInfoBlockProps> = ({
  username,
  passwordExpiration,
  onTokenGenerated,
}) => {
  const expirationDate = passwordExpiration ? new Date(passwordExpiration) : null;
  const formattedDate = expirationDate?.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  const formattedTime = expirationDate?.toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });

  return (
    <div className="flex flex-col gap-2 items-start mb-2 bg-ui-bg dark:bg-ui-secondary-bg-dark">
      <div className="text-text-primary dark:text-text-primary-dark">
        {passwordExpiration == null ? (
          <p className="font-medium">No access token created yet</p>
        ) : (
          <p className="font-medium">{`Token expires on: ${formattedDate} at ${formattedTime}`}</p>
        )}
      </div>
      <CreateAccessTokenButton
        username={username}
        onTokenGenerated={onTokenGenerated}
      />
    </div>
  );
};
