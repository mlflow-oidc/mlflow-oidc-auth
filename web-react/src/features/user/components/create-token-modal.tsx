import React, { useState, useCallback, useRef } from "react";
import { faCopy } from "@fortawesome/free-solid-svg-icons";
import { Button } from "../../../shared/components/button";
import { Modal } from "../../../shared/components/modal";
import { Input } from "../../../shared/components/input";
import { useToast } from "../../../shared/components/toast/use-toast";
import { createUserToken } from "../../../core/services/token-service";

interface CreateTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTokenCreated: () => void;
}

export const CreateTokenModal: React.FC<CreateTokenModalProps> = ({
  isOpen,
  onClose,
  onTokenCreated,
}) => {
  const today = new Date().toISOString().split("T")[0];
  const maxDate = new Date(new Date().setFullYear(new Date().getFullYear() + 1))
    .toISOString()
    .split("T")[0];

  const [tokenName, setTokenName] = useState<string>("");
  const [expirationDate, setExpirationDate] = useState<string>(maxDate);
  const [accessToken, setAccessToken] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const { showToast } = useToast();
  const tokenInputRef = useRef<HTMLInputElement>(null);

  const resetForm = useCallback(() => {
    setTokenName("");
    setExpirationDate(maxDate);
    setAccessToken("");
    setCopyFeedback(null);
  }, [maxDate]);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [resetForm, onClose]);

  const handleCreateToken = useCallback(async () => {
    if (!tokenName.trim()) {
      showToast("Token name is required", "error");
      return;
    }

    setIsLoading(true);
    setAccessToken("");

    try {
      const expirationDateObject = new Date(expirationDate);
      const response = await createUserToken({
        name: tokenName.trim(),
        expiration: expirationDateObject.toISOString(),
      });

      setAccessToken(response.token);
      showToast(`Token '${tokenName}' created successfully!`, "success");
      onTokenCreated();
    } catch (error) {
      console.error("Error creating token:", error);
      const errorMessage =
        error instanceof Error ? error.message : "Failed to create token";
      if (errorMessage.toLowerCase().includes("already exists")) {
        showToast(`Token with name '${tokenName}' already exists`, "error");
      } else {
        showToast(errorMessage, "error");
      }
    } finally {
      setIsLoading(false);
    }
  }, [tokenName, expirationDate, showToast, onTokenCreated]);

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
          setCopyFeedback("Failed!");
          setTimeout(() => setCopyFeedback(null), 2000);
        });
    }
  }, [accessToken]);

  const isFormValid = tokenName.trim().length > 0 && expirationDate;

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Create New Token">
      <p className="text-left text-base text-text-primary dark:text-text-primary-dark mb-4">
        Create a new named access token. Each token can have a unique name for
        easy identification (e.g., "CI/CD Pipeline", "Local Development").
      </p>

      <div className="space-y-4">
        <Input
          id="token-name"
          label="Token Name*"
          type="text"
          value={tokenName}
          onChange={(e) => setTokenName(e.target.value)}
          placeholder="my-token"
          required
          disabled={!!accessToken}
        />

        <Input
          id="expiration-date"
          label="Expiration Date*"
          type="date"
          value={expirationDate}
          onChange={(e) => setExpirationDate(e.target.value)}
          min={today}
          max={maxDate}
          required
          disabled={!!accessToken}
        />

        {!accessToken && (
          <div className="flex justify-end space-x-3 pt-4 border-t border-btn-secondary-border dark:border-btn-secondary-border-dark">
            <Button onClick={handleClose} variant="ghost">
              Cancel
            </Button>
            <Button
              onClick={handleCreateToken}
              disabled={isLoading || !isFormValid}
              variant="primary"
            >
              {isLoading ? "Creating..." : "Create Token"}
            </Button>
          </div>
        )}

        {accessToken && (
          <>
            <div className="relative">
              <Input
                ref={tokenInputRef}
                id="access-key"
                label="Access Token (copy now - shown only once)"
                type="text"
                readOnly
                value={accessToken}
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

            <div className="flex justify-end pt-4 border-t border-btn-secondary-border dark:border-btn-secondary-border-dark">
              <Button onClick={handleClose} variant="primary">
                Done
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};
