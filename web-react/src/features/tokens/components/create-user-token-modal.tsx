import React, { useCallback, useEffect, useRef, useState } from "react";
import { faCopy } from "@fortawesome/free-solid-svg-icons";
import { Modal } from "../../../shared/components/modal";
import { Button } from "../../../shared/components/button";
import { Input } from "../../../shared/components/input";
import { extractErrorMessage } from "../../../core/services/http";
import {
  createUserToken,
  type TokenOwner,
} from "../services/user-token-service";
import {
  endOfUtcDayIso,
  isWithinTokenDateBounds,
  tokenDateBounds,
} from "../utils/token-expiration";
import type { UserTokenWithSecret } from "../../../shared/types/user";

interface CreateUserTokenModalProps {
  isOpen: boolean;
  onClose: () => void;
  /** Called once the server has issued the token, while its secret is still on screen. */
  onCreated: (token: UserTokenWithSecret) => void;
  /** The account to issue for, or `undefined` for the signed-in user. */
  owner: TokenOwner;
}

type CopyState = "idle" | "copied" | "failed";

/**
 * Issue a named API token, then show its secret exactly once in the same dialog.
 *
 * One modal for both steps: the form is replaced by the secret on success and the footer
 * button becomes "Done". Closing the dialog discards the secret from memory, and a response
 * that arrives after the dialog was closed is never shown.
 */
export const CreateUserTokenModal: React.FC<CreateUserTokenModalProps> = ({
  isOpen,
  onClose,
  onCreated,
  owner,
}) => {
  const [bounds, setBounds] = useState(() => tokenDateBounds());
  const [name, setName] = useState("");
  const [expirationDate, setExpirationDate] = useState(bounds.defaultValue);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<UserTokenWithSecret | null>(null);
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const [wasOpen, setWasOpen] = useState(false);
  const secretRef = useRef<HTMLInputElement>(null);
  const copyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** Bumped on every close, so a create response that arrives after one is not displayed. */
  const generation = useRef(0);

  // Every opening starts from a fresh form with date bounds for the current UTC day: the dialog
  // stays mounted between uses, and "today" may have moved on since the last one.
  if (isOpen !== wasOpen) {
    setWasOpen(isOpen);
    if (isOpen) {
      const fresh = tokenDateBounds();
      setBounds(fresh);
      setName("");
      setExpirationDate(fresh.defaultValue);
      setIsSubmitting(false);
      setError(null);
      setCreated(null);
      setCopyState("idle");
    }
  }

  useEffect(() => {
    if (!isOpen) {
      generation.current += 1;
      if (copyTimer.current) clearTimeout(copyTimer.current);
    }
  }, [isOpen]);

  const trimmedName = name.trim();
  const expiration = endOfUtcDayIso(expirationDate);
  const dateInRange =
    expiration !== null && isWithinTokenDateBounds(expirationDate, bounds);
  const canSubmit = trimmedName.length > 0 && dateInRange && !isSubmitting;

  const handleClose = useCallback(() => {
    generation.current += 1;
    if (copyTimer.current) clearTimeout(copyTimer.current);
    setCreated(null);
    setCopyState("idle");
    onClose();
  }, [onClose]);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit || expiration === null) return;
    const requestGeneration = generation.current;
    setIsSubmitting(true);
    setError(null);
    try {
      const token = await createUserToken(owner, {
        name: trimmedName,
        expiration,
      });
      // The token exists server-side either way, so the owner list is told about it; only the
      // secret is withheld if the dialog was closed (e.g. Escape) while the request was running.
      onCreated(token);
      if (requestGeneration === generation.current) setCreated(token);
    } catch (err) {
      if (requestGeneration === generation.current) {
        setError(extractErrorMessage(err, "Failed to create token"));
      }
    } finally {
      if (requestGeneration === generation.current) setIsSubmitting(false);
    }
  };

  const handleCopy = () => {
    if (!created) return;
    if (copyTimer.current) clearTimeout(copyTimer.current);
    const fail = () => {
      setCopyState("failed");
      secretRef.current?.select();
    };
    if (!navigator.clipboard?.writeText) {
      fail();
      return;
    }
    navigator.clipboard.writeText(created.token).then(() => {
      setCopyState("copied");
      copyTimer.current = setTimeout(() => setCopyState("idle"), 2000);
    }, fail);
  };

  const title = created
    ? `Token "${created.name}" created`
    : owner === undefined
      ? "Create token"
      : `Create token for ${owner}`;

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title={title}>
      {created ? (
        <>
          <p className="text-sm text-status-danger dark:text-status-danger-dark font-medium">
            Copy this token now. It will not be shown again after you close this
            dialog.
          </p>
          <Input
            ref={secretRef}
            id="user-token-secret"
            label="Token"
            type="text"
            readOnly
            value={created.token}
            onFocus={(e) => e.currentTarget.select()}
            className="font-mono text-sm pr-12 cursor-default"
          >
            <div className="absolute right-1 bottom-1">
              <Button
                onClick={handleCopy}
                title="Copy token"
                aria-label="Copy token"
                variant="ghost"
                icon={faCopy}
              />
            </div>
          </Input>
          <p
            role="status"
            aria-live="polite"
            className={`text-sm min-h-5 ${
              copyState === "failed"
                ? "text-status-danger dark:text-status-danger-dark"
                : "text-green-600 dark:text-green-400"
            }`}
          >
            {copyState === "copied" && "Copied to clipboard."}
            {copyState === "failed" &&
              "Could not copy to the clipboard. The token is selected; copy it manually."}
          </p>
          <div className="flex justify-end">
            <Button onClick={handleClose} variant="primary">
              Done
            </Button>
          </div>
        </>
      ) : (
        <form
          className="space-y-5"
          onSubmit={(e) => {
            void handleSubmit(e);
          }}
        >
          <p className="text-left text-text-primary dark:text-text-primary-dark">
            Tokens authenticate API and CLI calls as{" "}
            {owner === undefined ? "you" : owner}. Every token expires at the
            end of the chosen day (UTC), at most one year from today.
          </p>
          <Input
            id="user-token-name"
            label="Name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="ci-pipeline"
            maxLength={255}
            required
            autoFocus
          />
          <Input
            id="user-token-expiration"
            label="Expires on (end of day, UTC)"
            type="date"
            value={expirationDate}
            onChange={(e) => setExpirationDate(e.target.value)}
            min={bounds.min}
            max={bounds.max}
            required
            error={
              expirationDate && !dateInRange
                ? `Pick a date between ${bounds.min} and ${bounds.max}.`
                : undefined
            }
            className="dark:scheme-dark cursor-pointer"
          />
          {error && (
            <p
              role="alert"
              className="text-sm text-status-danger dark:text-status-danger-dark"
            >
              {error}
            </p>
          )}
          <div className="flex justify-end space-x-3">
            <Button
              onClick={handleClose}
              variant="ghost"
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" disabled={!canSubmit}>
              {isSubmitting ? "Creating..." : "Create token"}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
};
