import React, { useRef, useState } from "react";
import { faCopy } from "@fortawesome/free-solid-svg-icons";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { Input } from "../../../shared/components/input";
import { useToast } from "../../../shared/components/toast/use-toast";
import type { ScimTokenWithSecret } from "../../../shared/types/scim";

interface ScimTokenSecretModalProps {
  isOpen: boolean;
  onClose: () => void;
  token: ScimTokenWithSecret | null;
}

export const ScimTokenSecretModal: React.FC<ScimTokenSecretModalProps> = ({
  isOpen,
  onClose,
  token,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);

  if (!token) return null;

  const handleCopy = () => {
    navigator.clipboard
      .writeText(token.token)
      .then(() => {
        setCopyFeedback("Copied!");
        showToast("Token copied to clipboard", "success");
        setTimeout(() => setCopyFeedback(null), 2000);
      })
      .catch((err) => {
        console.error("Could not copy token:", err);
        showToast("Failed to copy token", "error");
      });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Token "${token.name}"`}>
      <p className="text-sm text-status-danger dark:text-status-danger-dark font-medium">
        Copy this token now. For security, it cannot be retrieved again after
        you close this dialog.
      </p>

      <div className="relative">
        <Input
          ref={inputRef}
          id="scim-token-secret"
          label="Bearer token"
          type="text"
          readOnly
          value={token.token}
          className="font-mono text-sm pr-12 cursor-default"
        >
          <div className="absolute right-1 bottom-1">
            <Button
              onClick={handleCopy}
              title="Copy token"
              variant="ghost"
              icon={faCopy}
            />
          </div>
          {copyFeedback && (
            <span
              className="absolute right-10 bottom-1.5 text-xs px-2 py-1 rounded
                bg-btn-primary dark:bg-btn-primary-dark text-btn-primary-text dark:text-btn-primary-text-dark"
            >
              {copyFeedback}
            </span>
          )}
        </Input>
      </div>

      <div className="flex justify-end pt-4 border-t border-ui-secondary-bg dark:border-ui-secondary-bg-dark">
        <Button onClick={onClose} variant="primary">
          Done
        </Button>
      </div>
    </Modal>
  );
};
