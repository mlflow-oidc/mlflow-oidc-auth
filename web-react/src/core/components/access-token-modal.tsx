import React, { useState, useCallback, useRef, useEffect } from "react";
import { useUser } from "../hooks/use-user";
import { http } from "../services/http";
import { STATIC_API_ENDPOINTS } from "../configs/api-endpoints";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faCopy, faXmark } from "@fortawesome/free-solid-svg-icons";

interface TokenModel {
  token: string;
  message: string;
}

const requestAccessTokenApi = async (
  username: string,
  expiration: Date
): Promise<string> => {
  const tokenModel = await http<TokenModel>(
    STATIC_API_ENDPOINTS.CREATE_ACCESS_TOKEN,
    {
      method: "PATCH",
      body: JSON.stringify({
        username: username,
        expiration: expiration.toISOString(),
      }),
    }
  );

  if (!tokenModel.token) {
    throw new Error(
      "API response did not contain an access token (token field)."
    );
  }

  return tokenModel.token;
};

interface AccessTokenModalProps {
  onClose: () => void;
}

export const AccessTokenModal: React.FC<AccessTokenModalProps> = ({
  onClose,
}) => {
  const today = new Date().toISOString().split("T")[0];
  const maxDate = new Date(new Date().setFullYear(new Date().getFullYear() + 1))
    .toISOString()
    .split("T")[0];

  const { currentUser, refresh } = useUser();

  const [expirationDate, setExpirationDate] = useState<string>(maxDate);
  const [accessToken, setAccessToken] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [copyFeedback, setCopyFeedback] = useState<string | null>(null);
  const tokenInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = "unset";
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [onClose]);

  const handleRequestToken = useCallback(async () => {
    if (!currentUser) return null;

    setIsLoading(true);
    setAccessToken("");
    try {
      const expirationDateObject = new Date(expirationDate);

      const token = await requestAccessTokenApi(
        currentUser.username,
        expirationDateObject
      );
      setAccessToken(token);

      refresh();
    } catch (error) {
      console.error("Error requesting access token:", error);
    } finally {
      setIsLoading(false);
    }
  }, [expirationDate, currentUser, refresh]);

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
    <div
      className="fixed inset-0 z-50 overflow-y-auto bg-ui-bg-dark/50 dark:bg-ui-bg-dark/70 transition-opacity flex justify-center items-start pt-16 sm:pt-24 md:items-center md:pt-0"
      onClick={onClose}
    >
      <div
        className="relative bg-ui-bg dark:bg-ui-bg-dark rounded-lg shadow-xl w-full max-w-xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          className="absolute cursor-pointer top-0.5 right-1 text-text-primary dark:text-text-primary-dark hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark transition-colors p-1"
          onClick={onClose}
          aria-label="Close modal"
        >
          <FontAwesomeIcon icon={faXmark} size="1x" />
        </button>

        <div className="mb-2">
          <h4 className="text-lg text-ui-text dark:text-ui-text-dark">
            Generate Access Token for {currentUser?.username}
          </h4>
        </div>

        <div className="space-y-5">
          <p className="text-left text-base text-text-primary dark:text-text-primary-dark ">
            Use the form below to generate a new access token. Select an
            expiration date (maximum validity: 1 year) and click "Request
            Token".
          </p>

          <div className="flex items-end space-x-4">
            <div className="flex-grow">
              <label
                htmlFor="expiration-date"
                className="block text-sm text-left font-medium text-text-primary dark:text-text-primary-dark mb-1"
              >
                Expiration Date *
              </label>
              <input
                id="expiration-date"
                type="date"
                value={expirationDate}
                onChange={(e) => setExpirationDate(e.target.value)}
                min={today}
                max={maxDate}
                required
                className="w-full px-3 py-2 border rounded-md focus:outline-none 
                           text-ui-text dark:text-ui-text-dark
                           bg-ui-bg dark:bg-ui-secondary-bg-dark
                           border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                           focus:border-btn-primary dark:focus:border-btn-primary-dark
                           transition duration-150 ease-in-out cursor-pointer"
              />
            </div>

            <button
              type="button"
              onClick={handleRequestToken as () => void}
              disabled={isLoading || !expirationDate}
              className={`
                px-4 py-2 rounded-md font-medium transition-colors duration-200 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed 
                ${
                  isLoading
                    ? "opacity-70 cursor-not-allowed bg-btn-primary dark:bg-btn-primary-dark text-btn-primary-text dark:text-btn-primary-text-dark"
                    : "bg-btn-primary dark:bg-btn-primary-dark text-btn-primary-text dark:text-btn-primary-text-dark hover:bg-btn-primary-hover dark:hover:bg-btn-primary-hover-dark"
                }
              `}
            >
              {isLoading ? "Requesting..." : "Request Token"}
            </button>
          </div>

          <div className="relative">
            <label
              htmlFor="access-key"
              className="block text-sm font-medium text-text-primary dark:text-text-primary-dark mb-1 sr-only"
            >
              Access Key
            </label>
            <input
              ref={tokenInputRef}
              id="access-key"
              type="text"
              readOnly
              value={accessToken}
              placeholder={isLoading ? "Generating token..." : "Access Token"}
              className="w-full px-3 py-2 pr-12 border rounded-md focus:outline-none 
                         text-ui-text dark:text-ui-text-dark font-mono text-sm
                         bg-ui-secondary-bg dark:bg-ui-secondary-bg-dark
                         border-ui-secondary-bg dark:border-ui-secondary-bg-dark
                         read-only:cursor-default"
            />

            <button
              type="button"
              onClick={handleCopyToken}
              disabled={!accessToken}
              title="Copy Access Token"
              className="absolute right-2 top-2
                         text-text-primary dark:text-text-primary-dark hover:text-text-primary-hover dark:hover:text-text-primary-hover-dark cursor-pointer 
                         disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <FontAwesomeIcon icon={faCopy} size="1x" />
            </button>

            {copyFeedback && (
              <span
                className={`absolute right-10 bottom-2 bg-btn-primary dark:bg-btn-primary-dark text-btn-primary-text dark:text-btn-primary-text-dark text-xs px-2 py-1 rounded transition-opacity duration-300 ${
                  copyFeedback === "Copied!" ? "opacity-100" : "opacity-0"
                }`}
              >
                {copyFeedback}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
