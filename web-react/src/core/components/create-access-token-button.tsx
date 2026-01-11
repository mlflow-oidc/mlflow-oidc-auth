import React, { useState, useCallback } from "react";
import { AccessTokenModal } from "./access-token-modal";
import { Button } from "../../shared/components/button";
import { faPlus } from "@fortawesome/free-solid-svg-icons";

export const CreateAccessTokenButton: React.FC<{
  username: string;
  onTokenGenerated?: () => void;
}> = ({ username, onTokenGenerated }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const openModal = useCallback(() => setIsModalOpen(true), []);
  const closeModal = useCallback(() => setIsModalOpen(false), []);

  return (
    <>
      <Button
        onClick={openModal}
        variant="secondary"
        icon={faPlus}
      >
        Create Access Token
      </Button>

      {isModalOpen && (
        <AccessTokenModal
          onClose={closeModal}
          username={username}
          onTokenGenerated={onTokenGenerated}
        />
      )}
    </>
  );
};
