import React, { useState, useCallback, useRef } from "react";
import { useUser } from "../hooks/use-user";
import { http } from "../services/http";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";
import { faCopy } from "@fortawesome/free-solid-svg-icons";
import { Button } from "../../shared/components/button";
import { Modal } from "../../shared/components/modal";
import { Input } from "../../shared/components/input";
import { useToast } from "../../shared/components/toast/use-toast";

interface TokenModel {
  token: string;
  message: string;
}

const requestAccessTokenApi = async (username: string, expiration: Date): Promise<string> => {
  const tokenModel = await http<TokenModel>(STATIC_API_ENDPOINTS.CREATE_ACCESS_TOKEN, {
    method: "PATCH",
    body: JSON.stringify({
      username: username,
      expiration: expiration.toISOString(),
    }),
  });

  if (!tokenModel.token) {
    throw new Error("API response did not contain an access token (token field).");
  }

  return tokenModel.token;
};

interface AccessTokenModalProps {
  onClose: () => void;
  username: string;
  onTokenGenerated?: () => void;
}

export const AccessTokenModal: React.FC<AccessTokenModalProps> = ({
  onClose,
  username,
  onTokenGenerated,
}) => {
  const today = new Date().toISOString().split("T")[0];
  const maxDate = new Date(new Date().setFullYear(new Date().getFullYear() + 1))
    .toISOString()
    .split("T")[0];

  const { refresh } = useUser();

  const [expirationDate, setExpirationDate] = useState<string>(maxDate);
  const [accessToken, setAccessToken] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const { showToast } = useToast();
  const tokenInputRef = useRef<HTMLInputElement>(null);

  const handleRequestToken = useCallback(async () => {
    setIsLoading(true);
    setAccessToken("");
    try {
      const expirationDateObject = new Date(expirationDate);

      const token = await requestAccessTokenApi(username, expirationDateObject);
      setAccessToken(token);

      showToast("Access token generated successfully!", "success");
      refresh();
      onTokenGenerated?.();
    } catch (error) {
      console.error("Error requesting access token:", error);
      showToast("Failed to generate access token", "error");
    } finally {
      setIsLoading(false);
    }
  }, [expirationDate, username, refresh, showToast, onTokenGenerated]);

  const handleCopyToken = useCallback(() => {
    if (accessToken && tokenInputRef.current) {
      navigator.clipboard
        .writeText(accessToken)
        .then(() => {
          setCopyFeedback("Copied!");
          setTimeout(() => setCopyFeedback(null), 2000);
        })
        .catch((err) => {
          console.error("Could not copy text: ", err);
          setCopyFeedback("Failed to copy!");
          setTimeout(() => setCopyFeedback(null), 2000);
        });
    }
  }, [accessToken]);

  return (
    <Modal isOpen={true} onClose={onClose} title={`Generate Access Token for ${username}`}>
      <p className="text-left text-text-primary dark:text-text-primary-dark ">
        Use the form below to generate a new access token. Select an expiration date (maximum
        validity: 1 year) and click "Request Token".
      </p>

      <div className="flex items-end space-x-4">
        <Input
          id="expiration-date"
          label="Expiration Date*"
          type="date"
          value={expirationDate}
          onChange={(e) => setExpirationDate(e.target.value)}
          min={today}
          max={maxDate}
          required
          containerClassName="flex-grow"
          className="text-text-primary dark:text-text-primary-dark dark:scheme-dark cursor-pointer"
        />

        <Button
          onClick={handleRequestToken as () => void}
          disabled={isLoading || !expirationDate}
          variant="primary"
          className={`h-[42px] ${isLoading ? "opacity-70 cursor-not-allowed" : ""}`}
        >
          {isLoading ? "Requesting..." : "Request Token"}
        </Button>
      </div>

      <div className="relative">
        <Input
          ref={tokenInputRef}
          id="access-key"
          label="Access Key"
          type="text"
          readOnly
          value={accessToken}
          placeholder={isLoading ? "Generating token..." : "Access Token"}
          className="font-mono text-sm pr-12 cursor-default"
        >
          <div className="absolute right-1 bottom-1">
            <Button
              onClick={handleCopyToken}
              disabled={!accessToken}
              title="Copy Access Token"
              variant="ghost"
              icon={faCopy}
            />
          </div>
          {copyFeedback && (
            <span
              className={`absolute right-10 bottom-1.5 text-xs px-2 py-1 rounded
                bg-btn-primary dark:bg-btn-primary-dark text-btn-primary-text dark:text-btn-primary-text-dark
                transition-opacity duration-300
                ${copyFeedback === "Copied!" ? "opacity-100" : "opacity-0"}`}
            >
              {copyFeedback}
            </span>
          )}
        </Input>
      </div>
    </Modal>
  );
};
